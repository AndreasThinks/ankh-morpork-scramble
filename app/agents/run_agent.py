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
            # Authenticate with OpenRouter
            await self._apply_configuration()
            
            # Enable YOLO mode for complete auto-approval including MCP tools
            await self._enable_yolo_mode()

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

    async def _enable_yolo_mode(self) -> None:
        """Enable YOLO mode for complete auto-approval of all actions including MCP tools."""

        self.agent_logger.info("Enabling YOLO mode for auto-approval")
        await self._run_cli_command(
            [
                "cline",
                "config",
                "set",
                "yolo-mode-toggled=true",
            ],
            description="enable YOLO mode",
        )
    
    async def _apply_configuration(self) -> None:
        """Authenticate Cline with OpenRouter provider."""

        await self._run_cli_command(
            [
                "cline",
                "auth",
                "--provider",
                "openrouter",
                "--apikey",
                self.config.api_key,
                "--modelid",
                self.config.model
            ],
            mask_args=[self.config.api_key],
            description="authenticate with OpenRouter",
        )
    
    async def _create_task(self, instance_address: str, prompt: str) -> None:
        """Create a task on the specified Cline instance."""
        
        await self._run_cli_command(
            [
                "cline",
                "task",
                "new",
                prompt,
                "--address",
                instance_address,
                "-y",
                "-m",
                "act",
                "--setting",
                "auto-approval-settings.actions.use-mcp=true",
                "--setting",
                "auto-approval-settings.actions.execute-safe-commands=true",
            ],
            mask_args=[self.config.api_key],
            description="create task",
        )
    
    async def _follow_task(self, instance_address: str) -> None:
        """Follow the task execution until completion."""
        
        await self._run_cli_command(
            [
                "cline",
                "task",
                "view",
                "--follow-complete",
                "--address",
                instance_address,
            ],
            mask_args=[self.config.api_key],
            description="follow task",
        )

    def _write_mcp_settings(self) -> None:
        """Write the MCP server configuration consumed by Cline core."""

        settings_dir = self.cline_dir / "data" / "settings"
        settings_dir.mkdir(parents=True, exist_ok=True)
        settings_path = settings_dir / "cline_mcp_settings.json"

        data = {
            "mcpServers": {
                MCP_SERVER_NAME: {
                    "url": self.config.mcp_server_url,
                    "disabled": False,
                    "timeout": 120,
                    "alwaysAllow": [
                        "join_game",
                        "get_game_state",
                        "get_valid_actions",
                        "execute_action",
                        "end_turn",
                        "use_reroll",
                        "get_history",
                        "send_message",
                        "get_messages",
                    ],
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

            The Cline CLI is preconfigured with a remote MCP server named "{MCP_SERVER_NAME}" at
            {self.config.mcp_server_url}. Use only this server's tools to interact with the game. Available tools:
            join_game, get_game_state, get_valid_actions, execute_action, end_turn, use_reroll, get_history,
            send_message, get_messages.

            Workflow:
            1. Confirm the MCP server is reachable (list tools or call get_game_state).
            2. If the team is not yet registered, call join_game exactly once and verify via get_game_state that the
               join flag is set for your team.
            3. On every loop call get_game_state to understand the current phase, score, and whose turn it is.
            4. When it is YOUR turn, call get_valid_actions. Pick the first movable player and move them one square
               toward the opponent (i.e. {direction}) using execute_action with action_type="MOVE" and a
               target_position payload. Afterwards call end_turn immediately.
            5. When it is not your turn, acknowledge STATUS: WAITING after confirming the active team and continue
               polling the state until your turn resumes.
            6. Keep responses concise. Begin each status update with STATUS: followed by ACTION_TAKEN, WAITING, or
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
