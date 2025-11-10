"""Run an Ankh-Morpork Scramble agent using the Cline CLI."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import textwrap
from pathlib import Path
from typing import Iterable, Optional

import httpx

from app.agents.config import AgentConfig
from app.logging_utils import configure_root_logger

MCP_SERVER_NAME = "scramble"


async def _wait_for_server(base_url: str, timeout: float, *, prefix: str = "") -> None:
    """Wait for the MCP HTTP server to become available before launching Cline.

    Args:
        base_url: The HTTP base URL of the MCP server
        timeout: Maximum time to wait in seconds
        prefix: Optional logging prefix

    Raises:
        RuntimeError: If the server doesn't become ready within the timeout period
    """
    logger = logging.getLogger("app.agents")
    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(base_url, timeout=5)
                if response.status_code < 500:
                    context = f"{prefix} " if prefix else ""
                    logger.info("%sServer at %s is ready", context, base_url)
                    return
            except Exception:
                pass

            if asyncio.get_event_loop().time() > deadline:
                raise RuntimeError(f"Server at {base_url} did not become ready in time")

            await asyncio.sleep(1)


class ClineAgentRunner:
    """Thin wrapper around the Cline CLI for autonomous play."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        env: dict[str, str],
        cline_dir: Path,
        agent_logger: logging.Logger,
    ) -> None:
        self.config = config
        self.env = env
        self.cline_dir = cline_dir
        self.agent_logger = agent_logger
        self.cline_logger = logging.getLogger(f"app.agents.{config.team_id}.cline")

    async def run(self) -> None:
        """Configure the CLI, write MCP settings, and launch the task using instance management."""

        self._ensure_prerequisites()
        
        # Write MCP settings BEFORE starting instance (so it reads them on startup)
        self._write_mcp_settings()
        
        # Start a persistent Cline Core instance
        instance_address = await self._start_instance()
        self.agent_logger.info("Started Cline Core instance at %s", instance_address)
        
        try:
            # Configure OpenRouter API key for this instance
            await self._apply_configuration(instance_address)

            # Note: We do NOT enable YOLO mode here. Instead, we rely on granular
            # auto-approval settings in _create_task() to only auto-approve MCP tool
            # requests. This forces agents to use the MCP interface exclusively.

            # Build and create the task
            prompt = self._build_prompt()
            self.agent_logger.info("Creating Cline task with prompt:\n%s", prompt)

            await self._create_task(instance_address, prompt)
            
            # Follow the task until completion
            self.agent_logger.info("Following task execution...")
            await self._follow_task(instance_address)
            
        finally:
            # Clean up the instance
            await self._kill_instance(instance_address)

    def _ensure_prerequisites(self) -> None:
        if shutil.which("cline") is None:
            raise RuntimeError("cline executable not found on PATH. Ensure npm installed it correctly.")

        self.cline_dir.mkdir(parents=True, exist_ok=True)
        (self.cline_dir / "data" / "settings").mkdir(parents=True, exist_ok=True)

    async def _start_instance(self) -> str:
        """Start a persistent Cline Core instance and return its address."""
        
        process = await asyncio.create_subprocess_exec(
            "cline",
            "instance",
            "new",
            "--default",
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        output, _ = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"Failed to start Cline instance; exit code {process.returncode}")
        
        # Extract the instance address from output (format: "Address: 127.0.0.1:12345")
        output_text = output.decode(errors="ignore")
        self.cline_logger.info(output_text.strip())
        
        for line in output_text.split("\n"):
            if "Address:" in line:
                # Extract address after "Address: "
                parts = line.split("Address:")
                if len(parts) > 1:
                    address = parts[1].strip()
                    return address
        
        raise RuntimeError("Failed to extract instance address from output")
    
    async def _kill_instance(self, address: str) -> None:
        """Kill the Cline Core instance at the specified address."""
        
        self.agent_logger.info("Cleaning up Cline instance at %s", address)
        process = await asyncio.create_subprocess_exec(
            "cline",
            "instance",
            "kill",
            address,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        
        await process.wait()

    async def _enable_yolo_mode(self, instance_address: str) -> None:
        """Enable YOLO mode for complete auto-approval of all actions including MCP tools."""

        self.agent_logger.info("Enabling YOLO mode for auto-approval")
        await self._run_cli_command(
            [
                "cline",
                "config",
                "set",
                "yolo-mode-toggled=true",
                "--address",
                instance_address,
            ],
            description="enable YOLO mode",
        )
    
    async def _apply_configuration(self, instance_address: str) -> None:
        """Configure OpenRouter API key for the Cline instance."""

        # Set the OpenRouter API key as a config setting for this instance
        await self._run_cli_command(
            [
                "cline",
                "config",
                "set",
                f"open-router-api-key={self.config.api_key}",
                "--address",
                instance_address,
            ],
            mask_args=[self.config.api_key],
            description="configure OpenRouter API key",
        )
        
        # Note: auto-approval-settings.enabled is already true by default.
        # MCP auto-approval works through:
        # 1. MCP settings file's autoApprove array (written in _write_mcp_settings)
        # 2. Task setting auto-approval-settings.actions.use-mcp=true (set in _create_task)
        
        # Model selection happens via OPENROUTER_MODEL environment variable
    
    async def _create_task(self, instance_address: str, prompt: str) -> None:
        """Create a task on the specified Cline instance.

        Only auto-approves MCP tool requests, forcing agents to use the game's
        MCP interface exclusively. File operations and bash commands will require
        manual approval (but agents shouldn't need these).
        """

        await self._run_cli_command(
            [
                "cline",
                "task",
                "new",
                prompt,
                "--address",
                instance_address,
                "-m",
                "act",
                "--setting",
                "auto-approval-settings.actions.use-mcp=true",
                # Note: We explicitly do NOT auto-approve file operations or bash
                # commands, forcing agents to rely solely on MCP tools for gameplay
            ],
            mask_args=[self.config.api_key],
            description="create task",
        )
    
    async def _follow_task(self, instance_address: str) -> None:
        """Follow the task execution until completion.

        MCP tools are auto-approved via settings. If agents try to use non-MCP
        tools (files, bash), we actively reject them to keep the agent moving.
        """

        self.agent_logger.info("Following task execution (MCP auto-approved, non-MCP auto-rejected)...")

        process = await asyncio.create_subprocess_exec(
            "cline",
            "task",
            "view",
            "--follow-complete",
            "--address",
            instance_address,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Monitor stdout for approval requests and auto-reject non-MCP ones
        tasks = []
        if process.stdout is not None:
            tasks.append(asyncio.create_task(
                self._monitor_and_reject_non_mcp(process.stdout, instance_address)
            ))
        if process.stderr is not None:
            tasks.append(asyncio.create_task(
                self._stream_output(process.stderr, self.cline_logger.error)
            ))

        # Wait for all tasks to complete
        if tasks:
            await asyncio.gather(*tasks)

        return_code = await process.wait()
        if return_code != 0:
            raise RuntimeError(f"Failed to follow task; exit code {return_code}")
    
    async def _monitor_and_reject_non_mcp(self, stream: asyncio.StreamReader, instance_address: str) -> None:
        """Monitor output stream and actively reject non-MCP tool requests.

        MCP tools are already auto-approved via settings. This method detects when
        agents try to use non-MCP tools (files, bash) and sends an active rejection
        to keep the agent from hanging.
        """

        pending_request = None

        while True:
            line = await stream.readline()
            if not line:
                break

            text = line.decode(errors="ignore").rstrip()
            masked_text = self._mask_text(text)
            self.cline_logger.info(masked_text)

            # Detect approval request patterns
            if "Cline is requesting approval" in text:
                # Check if this is a non-MCP tool request
                if "read file" in text.lower() or "write file" in text.lower():
                    pending_request = "file"
                    self.agent_logger.warning("Detected file operation request - will auto-reject")
                elif "execute command" in text.lower() or "run command" in text.lower():
                    pending_request = "bash"
                    self.agent_logger.warning("Detected bash command request - will auto-reject")
                # MCP tools are auto-approved by settings, so we don't need to handle them

            # Auto-reject non-MCP requests when we see the instruction
            if pending_request and ("Use cline task send" in text):
                request_type = pending_request
                pending_request = None
                await self._auto_reject(instance_address, request_type)

    async def _monitor_and_approve(self, stream: asyncio.StreamReader, instance_address: str) -> None:
        """Monitor output stream for approval requests and automatically approve them.

        NOTE: This method is no longer used. Kept for reference.
        """

        approval_pending = False

        while True:
            line = await stream.readline()
            if not line:
                break

            text = line.decode(errors="ignore").rstrip()
            masked_text = self._mask_text(text)
            self.cline_logger.info(masked_text)

            # Detect approval request pattern
            if "Cline is requesting approval" in text or "requesting approval to use this tool" in text:
                approval_pending = True
                self.agent_logger.info("Detected approval request - auto-approving...")

            # Auto-approve when we see the approval request
            if approval_pending and ("Use cline task send --approve" in text or "cline task send --approve" in text):
                approval_pending = False
                await self._auto_approve(instance_address)
    
    async def _auto_reject(self, instance_address: str, request_type: str) -> None:
        """Automatically reject non-MCP tool requests.

        Args:
            instance_address: The Cline instance address
            request_type: Type of rejected request (file, bash, etc.)
        """

        rejection_message = (
            f"This {request_type} operation is not allowed. "
            f"You can only use MCP tools to interact with the game. "
            f"Please use the available MCP tools like get_game_state, execute_action, etc."
        )

        try:
            process = await asyncio.create_subprocess_exec(
                "cline",
                "task",
                "send",
                "--reject",
                rejection_message,
                "--address",
                instance_address,
                env=self.env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.agent_logger.info(f"Successfully auto-rejected {request_type} request")
            else:
                error_text = stderr.decode(errors="ignore") if stderr else "Unknown error"
                self.agent_logger.error(f"Failed to auto-reject: {error_text}")

        except Exception as e:
            self.agent_logger.error(f"Exception during auto-rejection: {e}")

    async def _auto_approve(self, instance_address: str) -> None:
        """Automatically approve the pending tool use request.

        NOTE: This method is no longer used but kept for reference.
        MCP tools are auto-approved via task settings.
        """

        try:
            process = await asyncio.create_subprocess_exec(
                "cline",
                "task",
                "send",
                "--approve",
                "--address",
                instance_address,
                env=self.env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.agent_logger.info("Successfully auto-approved MCP tool request")
            else:
                error_text = stderr.decode(errors="ignore") if stderr else "Unknown error"
                self.agent_logger.error(f"Failed to auto-approve: {error_text}")

        except Exception as e:
            self.agent_logger.error(f"Exception during auto-approval: {e}")

    def _write_mcp_settings(self) -> None:
        """Write the MCP server configuration consumed by Cline core.
        
        The MCP server now runs on a separate port (default 8001) and auto-generates
        tools from FastAPI endpoints.
        """
        settings_dir = self.cline_dir / "data" / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "cline_mcp_settings.json"

        data = {
            "mcpServers": {
                MCP_SERVER_NAME: {
                    "url": self.config.mcp_server_url,
                    "disabled": False,
                    "timeout": 120,
                }
            }
        }

        settings_json = json.dumps(data, indent=2)
        settings_path.write_text(settings_json)
        self.agent_logger.info("Updated MCP configuration at %s", settings_path)
        self.agent_logger.info("MCP settings content:\n%s", settings_json)
        
        # Verify file was written
        if settings_path.exists():
            self.agent_logger.info("MCP settings file verified to exist at %s", settings_path)
        else:
            self.agent_logger.error("MCP settings file was NOT created at %s", settings_path)

    def _build_prompt(self) -> str:
        direction = (
            "increase the x coordinate by 1"
            if self.config.team_direction == 1
            else "decrease the x coordinate by 1"
        )

        return textwrap.dedent(
            f"""
            You are an autonomous coach for Ankh-Morpork Scramble controlling team {self.config.team_name}
            (ID {self.config.team_id}). The current game identifier is {self.config.game_id}.

            You have access to MCP tools to interact with the game server.  Use them to play the game.  You should also be able to use resources.  

            If you cannot access these tools, explain the issue in your status updates.

            Workflow:
            1. Call get_game_state to confirm connectivity. If the team is not yet registered, call join_game exactly
               once and verify that your team now appears in the game state.
            2. While the phase is DEPLOYMENT you must build your roster:
               • Use get_team_budget and get_available_positions to understand your gold and shopping options.
               • Purchase players with buy_player until you have at least eleven active players (or you run out of
                 valid slots). Prioritise cheaper positions if you need a fallback plan.
               • Optionally purchase rerolls with buy_reroll if budget permits.
               • When you are ready, place your squad with place_players and then call ready_to_play. Wait until the
                 game reports both teams are ready or the phase advances to KICKOFF.
            3. Once the match is live, loop on get_game_state to understand the current phase, score, and whose turn it
               is.
            4. When it is YOUR turn, call get_valid_actions. Pick the first movable player and move them one square
               toward the opponent (i.e. {direction}) using execute_action with action_type="MOVE" and a
               target_position payload. Afterwards call end_turn immediately.
            5. After taking an action, use send_message to share your strategic thinking with spectators. Send concise
               messages explaining what you did and why. For example: "Moved Lineman forward to support our advance"
               or "Positioning Catcher near the ball carrier for a pass option". This helps fans follow your strategy!
            6. When it is not your turn, acknowledge STATUS: WAITING after confirming the active team and continue
               polling the state until your turn resumes.
            7. Keep responses concise. Begin each status update with STATUS: followed by ACTION_TAKEN, WAITING, or
               COMPLETE. Mention the MCP tools you invoked in that turn.

            Stop once the match ends, the game reports a winner, or you cannot perform further actions. Provide a
            final STATUS: COMPLETE summary including the last scoreline.
            """
        ).strip()

    async def _run_cli_command(
        self,
        args: list[str],
        *,
        stdin_text: Optional[str] = None,
        mask_args: Optional[Iterable[str]] = None,
        description: str,
    ) -> None:
        display_cmd = " ".join(self._mask_argument(arg, mask_args) for arg in args)
        self.agent_logger.info("Executing: %s", display_cmd)

        process = await asyncio.create_subprocess_exec(
            *args,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if stdin_text is not None else None,
        )

        tasks = []
        if process.stdout is not None:
            tasks.append(asyncio.create_task(self._stream_output(process.stdout, self.cline_logger.info)))
        if process.stderr is not None:
            tasks.append(asyncio.create_task(self._stream_output(process.stderr, self.cline_logger.error)))

        if stdin_text is not None and process.stdin is not None:
            process.stdin.write(stdin_text.encode())
            await process.stdin.drain()
            process.stdin.close()

        if tasks:
            await asyncio.gather(*tasks)

        return_code = await process.wait()
        if return_code != 0:
            raise RuntimeError(f"Failed to {description}; exit code {return_code}")

    async def _stream_output(self, stream: asyncio.StreamReader, log_method) -> None:
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode(errors="ignore").rstrip()
            log_method(self._mask_text(text))

    def _mask_argument(self, value: str, mask_args: Optional[Iterable[str]]) -> str:
        if not mask_args:
            return value
        masked = value
        for secret in mask_args:
            if secret:
                masked = masked.replace(secret, "[REDACTED]")
        return masked

    def _mask_text(self, value: str) -> str:
        masked = value
        if self.config.api_key:
            masked = masked.replace(self.config.api_key, "[REDACTED]")
        return masked


async def run() -> None:
    config = AgentConfig.from_env()
    log_file = configure_root_logger(
        service_name=f"agent-{config.team_id}",
        env_prefix="AGENT_",
        default_level=os.getenv("AGENT_LOG_LEVEL", "INFO"),
    )

    agent_logger = logging.getLogger(f"app.agents.{config.team_id}")
    prefix = f"[{config.game_id}][{config.team_id}]"
    if log_file:
        agent_logger.info("%s Log file initialised at %s", prefix, log_file)

    # Wait for the MCP server to be ready before launching Cline
    await _wait_for_server(config.http_base_url, config.startup_timeout, prefix=prefix)

    env = os.environ.copy()
    cline_dir = Path(env.get("CLINE_DIR", ""))
    if not cline_dir:
        cline_dir = Path("/tmp") / f"cline-{config.team_id}"
    env["CLINE_DIR"] = str(cline_dir)
    env.setdefault("POSTHOG_TELEMETRY_ENABLED", "false")
    env.setdefault("CLINE_DISABLE_AUTO_UPDATE", "1")
    env.setdefault("CLINE_CLI_DISABLE_AUTO_UPDATE", "1")

    # Configure OpenRouter headers required by the API
    # OpenRouter requires HTTP-Referer and X-Title headers for authentication
    # These are passed as default headers to the OpenAI-compatible client
    default_headers = json.dumps({
        "HTTP-Referer": config.http_referer,
        "X-Title": config.app_title,
    })
    env["OPENAI_DEFAULT_HEADERS"] = default_headers

    runner = ClineAgentRunner(config, env=env, cline_dir=cline_dir, agent_logger=agent_logger)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(run())
