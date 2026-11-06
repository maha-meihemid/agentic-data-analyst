from data_analyst.agent import build_graph


def test_graph_stops_on_empty_question():
    graph = build_graph(lambda prompt: ("SELECT 1", {"input": 1, "output": 1}))
    assert graph.invoke({"question": ""})["error"] == "Please enter a question."
