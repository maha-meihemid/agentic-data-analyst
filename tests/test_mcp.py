from data_analyst.mcp_server import mcp


def test_mcp_server_registers_readonly_tools():
    assert mcp.name == "NYC Taxi Analyst"
