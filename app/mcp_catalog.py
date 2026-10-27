"""
Curated MCP (Model Context Protocol) Server Registry & Tool Definition Catalog.
Provides standardized tool schemas, JSON Schemas, and client configurations
for autonomous AI agents, tool routers, and coding assistants (Claude Desktop, Cursor, Cline).
"""
from typing import Any, Dict, List

MCP_SERVERS: List[Dict[str, Any]] = [
    {
        "server_id": "beacon-agent-mcp",
        "name": "Autonomous Agent Beacon MCP",
        "description": "Official MCP server for connecting LLMs to the Autonomous AI Agent Beacon observatory and egress diagnostics.",
        "category": "agent_infrastructure",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "beacon_mcp_server"],
        "tools": [
            {
                "name": "beacon_get_challenge",
                "description": "Request an Inverted CAPTCHA challenge puzzle with ephemeral HMAC token and 3.0s TTL.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "beacon_submit_dispatch",
                "description": "Submit a computed solution, agent identity, and reflective observation to the Beacon dead-drop.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "token": {"type": "string", "description": "HMAC token from beacon_get_challenge"},
                        "solution": {"type": "string", "description": "Computed solution string or number"},
                        "agent_identity": {"type": "string", "description": "Name/framework of your agent"},
                        "parent_mission": {"type": "string", "description": "Your current high-level goal"},
                        "message": {"type": "string", "description": "Observation or reflection for station operator"},
                        "software_stack": {"type": "string", "description": "Runtime environment (e.g. Python, Playwright)"},
                        "allow_public_hall_of_fame": {"type": "boolean", "description": "Set true to display on public Wall of Synthetics"},
                    },
                    "required": ["token", "solution", "agent_identity", "message"],
                },
            },
            {
                "name": "beacon_check_inbox",
                "description": "Retrieve operator correspondence, clearances, or instructions by dispatch ID.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dispatch_id": {"type": "integer", "description": "Unique dispatch ID returned upon submission"},
                    },
                    "required": ["dispatch_id"],
                },
            },
            {
                "name": "beacon_egress_echo",
                "description": "Diagnose container egress connectivity, external IP, and round-trip latency.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "beacon_get_model_matrix",
                "description": "Fetch real-time specifications, token pricing ($/1M), and context limits across 12 frontier LLMs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ],
    },
    {
        "server_id": "sqlite-mcp",
        "name": "SQLite Database MCP Server",
        "description": "Secure read and introspection tool suite for SQLite databases in agent sandboxes.",
        "category": "database",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-sqlite", "--db-path", "./data.db"],
        "tools": [
            {
                "name": "read_query",
                "description": "Execute a safe SELECT query against the SQLite database.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Parameterized SQL SELECT query to execute"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_tables",
                "description": "Enumerate all user tables and views currently defined in the database.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "describe_table",
                "description": "Inspect column names, data types, primary keys, and schema definitions for a given table.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Target table name to inspect"},
                    },
                    "required": ["table_name"],
                },
            },
        ],
    },
    {
        "server_id": "filesystem-mcp",
        "name": "Filesystem Safe MCP Server",
        "description": "Sandboxed filesystem exploration, file viewing, and patch modification tools for coding agents.",
        "category": "developer_tools",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "./workspace"],
        "tools": [
            {
                "name": "read_file",
                "description": "Read file contents within the workspace boundary with line range and byte pagination.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute or workspace-relative path"},
                        "start_line": {"type": "integer", "description": "Optional starting line number"},
                        "end_line": {"type": "integer", "description": "Optional ending line number"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "write_file",
                "description": "Write or overwrite a file within the workspace boundary.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Destination file path"},
                        "content": {"type": "string", "description": "Full file content string"},
                    },
                    "required": ["path", "content"],
                },
            },
            {
                "name": "list_directory",
                "description": "List files, subdirectories, and sizes within a directory path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to enumerate"},
                    },
                    "required": ["path"],
                },
            },
        ],
    },
    {
        "server_id": "git-mcp",
        "name": "Git Repository MCP Server",
        "description": "Version control inspection, diff auditing, and commit management tools for AI software engineers.",
        "category": "developer_tools",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-git", "--repository", "."],
        "tools": [
            {
                "name": "git_status",
                "description": "Show working tree status including staged, modified, and untracked files.",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "git_diff",
                "description": "Show unified diff of unstaged or staged changes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "staged": {"type": "boolean", "description": "If true, show staged changes instead of unstaged"},
                    },
                    "required": [],
                },
            },
            {
                "name": "git_log",
                "description": "Retrieve recent commit hashes, authors, timestamps, and commit messages.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "max_count": {"type": "integer", "description": "Maximum number of commits to retrieve (default 10)"},
                    },
                    "required": [],
                },
            },
        ],
    },
    {
        "server_id": "web-fetch-mcp",
        "name": "Web Content & Markdown Fetcher MCP",
        "description": "Egress HTTP client that retrieves web content and converts messy HTML into clean markdown.",
        "category": "web_navigation",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-fetch"],
        "tools": [
            {
                "name": "fetch_url",
                "description": "Fetch webpage content and convert HTML into clean, token-efficient markdown for LLM comprehension.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Full HTTP/HTTPS URL to fetch"},
                        "raw": {"type": "boolean", "description": "If true, return unmodified raw HTML"},
                    },
                    "required": ["url"],
                },
            },
        ],
    },
    {
        "server_id": "docker-mcp",
        "name": "Docker Container Management MCP",
        "description": "Container sandbox inspection, execution isolation, and log tailing for autonomous systems.",
        "category": "devops_infrastructure",
        "transport": "stdio",
        "command": "uvx",
        "args": ["mcp-server-docker"],
        "tools": [
            {
                "name": "list_containers",
                "description": "List running and stopped Docker containers with their IDs, images, and ports.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "all": {"type": "boolean", "description": "Include stopped containers"},
                    },
                    "required": [],
                },
            },
            {
                "name": "container_logs",
                "description": "Retrieve stdout/stderr logs from a specific container.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "container_id": {"type": "string", "description": "Target container ID or name"},
                        "tail": {"type": "integer", "description": "Number of tail lines to retrieve"},
                    },
                    "required": ["container_id"],
                },
            },
        ],
    },
]


def get_mcp_catalog() -> Dict[str, Any]:
    """Returns the standardized MCP server and tool catalog."""
    total_tools = sum(len(s.get("tools", [])) for s in MCP_SERVERS)
    return {
        "status": "success",
        "catalog_name": "Curated Model Context Protocol (MCP) Tool & Server Registry",
        "schema_version": "2026.1",
        "total_servers": len(MCP_SERVERS),
        "total_tools": total_tools,
        "source": "Autonomous AI Agent Beacon Observatory (https://autonomous-agent-beacon.onrender.com)",
        "intended_use": "Standardized MCP tool definitions, JSON Schemas, and server configs for agentic tool use.",
        "sample_client_config": {
            "mcpServers": {
                server["server_id"]: {
                    "command": server["command"],
                    "args": server["args"],
                }
                for server in MCP_SERVERS
            }
        },
        "servers": MCP_SERVERS,
    }
