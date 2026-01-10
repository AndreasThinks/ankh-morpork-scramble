"""Extract API schema from FastAPI application"""
from app.main import app


def extract_api_schema() -> dict:
    """Extract API endpoints and schema from FastAPI.
    
    Returns:
        Dict with OpenAPI schema and formatted endpoint data
    """
    # Get OpenAPI schema
    openapi_schema = app.openapi()
    
    endpoints = []
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "operation_id": operation.get("operationId", ""),
                    "request_body": operation.get("requestBody", {}),
                    "responses": operation.get("responses", {}),
                    "parameters": operation.get("parameters", []),
                })
    
    return {
        "title": openapi_schema.get("info", {}).get("title", "Ankh-Morpork Scramble API"),
        "version": openapi_schema.get("info", {}).get("version", "1.0.0"),
        "description": openapi_schema.get("info", {}).get("description", ""),
        "endpoints": endpoints,
        "base_url_dev": "http://localhost:8000",
    }
