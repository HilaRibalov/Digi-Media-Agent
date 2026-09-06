# generate_diagram.py
from agent import app


def generate_full_mermaid():
    """
    Extracts nodes from the compiled LangGraph app and manually
    constructs complete Mermaid flowchart syntax, including routing edges.
    """
    graph = app.get_graph()

    mermaid_lines = [
        "graph TD;",
        "\t%% Node Definitions",
        "\t__start__([Start])",
        "\t__end__([End])"
    ]

    # Extract registered nodes dynamically from the app
    for node_id in graph.nodes.keys():
        if node_id not in ["__start__", "__end__"]:
            mermaid_lines.append(f"\t{node_id}[{node_id}]")

    mermaid_lines.append("\n\t%% Workflow Edges & Routing Rules")

    # 1. Routing from START
    mermaid_lines.append("\t__start__ -->|Approved| gather_updates")
    mermaid_lines.append("\t__start__ -->|New Event| find_space_to_save")

    # 2. Human-in-the-loop path approval loop
    mermaid_lines.append("\tfind_space_to_save -->|Feedback Given| find_space_to_save")
    mermaid_lines.append("\tfind_space_to_save -->|Path Approved| create_drive_space")

    # 3. Setup flow: folder creation leads directly to initial notifications
    mermaid_lines.append("\tcreate_drive_space --> send_reminders")

    # 4. Processing flow: data collection and reasoning
    mermaid_lines.append("\tgather_updates --> evaluate_and_filter")
    mermaid_lines.append("\tevaluate_and_filter --> reply_to_messages")

    # 5. Main router decision branches
    mermaid_lines.append("\treply_to_messages -->|Finished / List Empty| __end__")
    mermaid_lines.append("\treply_to_messages -->|Message Only Wakeup| __end__")
    mermaid_lines.append("\treply_to_messages -->|Reminder Count >= 3| escalate_to_human")
    mermaid_lines.append("\treply_to_messages -->|Timer Wakeup| send_reminders")

    # 6. Terminal nodes
    mermaid_lines.append("\tsend_reminders --> __end__")
    mermaid_lines.append("\tescalate_to_human --> __end__")

    # Visual styling classes
    mermaid_lines.append("\n\t%% Styling")
    mermaid_lines.append("\tclassDef default fill:#f2f0ff,stroke:#5c4dff,stroke-width:1.5px;")
    mermaid_lines.append("\tclassDef terminal fill:#bfb6fc,stroke:#3b2fc9,stroke-width:2px;")
    mermaid_lines.append("\tclass __start__,__end__ terminal;")

    diagram_output = "\n".join(mermaid_lines)

    print("\n--- Copy the text below into mermaid.live ---\n")
    print(diagram_output)
    print("\n-----------------------------------------------\n")


if __name__ == "__main__":
    generate_full_mermaid()