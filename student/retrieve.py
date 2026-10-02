import numpy as np
import sys
sys.path.append("../../")

from student.cognitive_module.memory import *
from student.cognitive_module.scratch import *
from student.cognitive_module.student import *
from student.prompt.run_ds_prompt import *

# TODO: First based on keyword search and, if not available, on weighting and retrieval。
# If you retrieve the keyword, it's right there
async def retrieve(student, perceived_node):
    """
    Retrieving from memory perceived_node(ConceptNode Category)Relevant information。
    Search here only by keyword。
    For the time being, only relevant ideas and types of knowledge can be retrieved）
    INPUT:
        student: Student Category
        perceived_node: ConceptNode Category
    OUTPUT:
        relevant_mem: {Description of current node}: {Type of node retrieved: List of retrieved nodes}}

    """
    if perceived_node is None:
        print("No information is detectable and cannot be retrieved。")
        return {}

    print(f"{student.name}In search")

    relevant_mem = {perceived_node.content: {}}
    keywords = perceived_node.keywords
    print(f"Keyword to retrieve node: {keywords}")

    # Retrieving relevant ideas
    relevant_thoughts = student.mem.retrieve_relevant_thoughts(keywords)
    if relevant_thoughts:
        relevant_mem[perceived_node.content]["thought"] = relevant_thoughts

    print(f"Retrieved thought: {relevant_thoughts}")
    # If no relevant ideas are retrieved, you can try to retrieve the relevant knowledge
    if not relevant_thoughts:
        print("No ideas were retrieved and attempts to retrieve knowledge were made。")

    # Retrieving relevant knowledge
    relevant_knowledge = student.mem.retrieve_relevant_knowledge(keywords)
    if relevant_knowledge:
        relevant_mem[perceived_node.content]["knowledge"] = relevant_knowledge

    print(f"Information retrieved: {relevant_knowledge}")


    # Other types of memory can be retrieved as needed, for example event, chat Wait
    # relevant_events = student.mem.retrieve_relevant_events(keywords)
    # if relevant_events:
    #     relevant_mem[perceived_node.description]["event"] = relevant_events

    return relevant_mem






def cosine_similarity(vec1, vec2):
    """
    Calculates cosine similarity of two vectors。
    """
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def extract_recency(student, nodes):
    """
    nodes For a series of chronological memory nodes
    OUTPUT:
        recency_out: Dictionary with node.node_id， Value recency Value(float)
    """
    recency_out = {}

    recency_vals = [student.scratch.recency_decay ** i
                    for i in range(1, len(nodes) + 1)]

    for i, node in enumerate(nodes):
        recency_out[node.node_id] = recency_vals[i]

    return recency_out

def extract_importance(student, nodes):
    """
    As above
    """
    importance_out = {}
    for i, node in enumerate(nodes):
        importance_out[node.node_id] = node.importance

    return importance_out

async def extract_relevance(student, nodes, focus):
    """
    As above, one more is needed here focus Strings for calculating their and memory nodes embedding Similarity。
    INPUT:
        student: Student Category
        nodes: Series ConceptNode Examples of categories
        focus: string, Focus information needed to calculate relevance
    OUTPUT:
        relevance_out: Dictionary with node.node_id，Value relevance Value(float)
    """
    focus_embedding = await get_local_embedding(focus)

    relevance_out = {}
    for i, node in enumerate(nodes):
        node_embedding = student.mem.embeddings[node.embedding_key]
        relevance_out[node.node_id] = cosine_similarity(focus_embedding, node_embedding)

    return relevance_out

def normalize_dict_floats(d, target_min, target_max):
    """
    Standardize a dictionary to the specified range[min_value, max_value]。
    INPUT:
        d: Dictionary with node_id，Value as float
        min_value: float, Min
        max_value: float, Maximum
    OUTPUT:
        normalized_d: Dictionary with node_id，Value is standardized float
    """
    if not d or len(d) == 0:
        return {}

    min_val = min(val for val in d.values())
    max_val = max(val for val in d.values())
    range_val = max_val - min_val

    if range_val == 0:
        for key, val in d.items():
            d[key] = (target_max - target_min)/2
    else:
        for key, val in d.items():
            d[key] = ((val - min_val) * (target_max - target_min)
                    / range_val + target_min)
    return d

def top_x_values(d, x):
    """
    Extract from dictionary x Max。
    INPUT:
        d: Dictionary with node_id，Value as float
        x: int, Maximum number of values to extract
    OUTPUT:
        top_x: Maximum value x Dictionary of Items, with node_id，Value as float
    """
    top_x = dict(sorted(d.items(),
                        key=lambda item: item[1],
                        reverse=True)[:x])
    return top_x

async def further_retrieve(student, focus_info, n_count=10):
    """
    Retrieving from memory focus_info Relevant information。
    INPUT:
        student: Student Category
        focus_info: list of string, According to students
    OUTPUT:
        relevant_mem: {Concerns: [Retrieved ConceptNode Category List of Examples]}
    """
    retrieved_mem = {}
    for focus_point in focus_info:
        # One nodes List, where each element is also[i.last_accessed, i] Form
        # Here i Yes ConceptNode Examples of categories
        nodes = [[i.last_accessed, i]
                 for i in student.mem.seq_thought + student.mem.seq_knowledge]
        # Sort in chronological order
        nodes.sort(key=lambda x: x[0], reverse=True)
        # Extract Nodes
        nodes = [i[1] for i in nodes]

        # Extract recency, importance, relevance
        recency_out = extract_recency(student, nodes)
        recency_out = normalize_dict_floats(recency_out, 0, 1)
        importance_out = extract_importance(student, nodes)
        importance_out = normalize_dict_floats(importance_out, 0, 1)
        relevance_out = await extract_relevance(student, nodes, focus_point)
        relevance_out = normalize_dict_floats(relevance_out, 0, 1)

        weights = [0.5, 2, 2]
        master_out = dict()
        for key in recency_out.keys():
            master_out[key] = (weights[0] * recency_out[key] * student.scratch.recency_w +
                                weights[1] * importance_out[key] * student.scratch.importance_w +
                                weights[2] * relevance_out[key] * student.scratch.relevance_w)

        # According to master_out value to sort
        master_out = top_x_values(master_out, n_count)
        master_nodes = [student.mem.id_to_node[i] for i in list(master_out.keys())]

        # Update the recent access to the retrieved memory nodes
        for node in master_nodes:
            node.last_accessed = student.scratch.current_time

        retrieved_mem[focus_point] = master_nodes

    return retrieved_mem

async def further_retrieve_with_precomputed_embedding(student, focus_text, focus_embedding, n_count=10):
    """
    Use precalculated embedding Search and avoid double counting
    INPUT:
        student: Student Category
        focus_text: str, Focus Text (for displaying）
        focus_embedding: list, Projected embedding Vector
        n_count: int, Number of searches
    OUTPUT:
        master_nodes: list, Retrieved ConceptNode Examples List
    """
    # Fetch All Memory Nodes
    nodes = [[i.last_accessed, i] for i in student.mem.seq_thought + student.mem.seq_knowledge]

    if not nodes:
        print(f"Students {student.name} No memory")
        return []

    # Sort by Time
    nodes.sort(key=lambda x: x[0], reverse=True)
    nodes = [i[1] for i in nodes]

    # Calculates the dimension fractions
    recency_out = extract_recency(student, nodes)
    recency_out = normalize_dict_floats(recency_out, 0, 1)

    importance_out = extract_importance(student, nodes)
    importance_out = normalize_dict_floats(importance_out, 0, 1)

    # Use precalculated embedding Calculate Relevance
    relevance_out = extract_relevance_with_precomputed_embedding(
        student, nodes, focus_embedding
    )
    relevance_out = normalize_dict_floats(relevance_out, 0, 1)

    # Comprehensive score
    weights = [0.5, 2, 2]
    master_out = dict()
    for key in recency_out.keys():
        master_out[key] = (
            weights[0] * recency_out[key] * student.scratch.recency_w +
            weights[1] * importance_out[key] * student.scratch.importance_w +
            weights[2] * relevance_out[key] * student.scratch.relevance_w
        )

    # Selection top-N
    master_out = top_x_values(master_out, n_count)
    master_nodes = [student.mem.id_to_node[i] for i in list(master_out.keys())]

    # Update access time
    for node in master_nodes:
        node.last_accessed = student.scratch.current_time

    return master_nodes

def extract_relevance_with_precomputed_embedding(student, nodes, focus_embedding):
    """
    Use precalculated embedding Calculate Relevance
    INPUT:
        student: Student Category
        nodes: list, ConceptNode Examples List
        focus_embedding: list, Projected embedding Vector
    OUTPUT:
        relevance_out: dict, Relevance Dictionary
    """
    relevance_out = {}

    for node in nodes:
        try:
            node_embedding = student.mem.embeddings[node.embedding_key]
            relevance_out[node.node_id] = cosine_similarity(focus_embedding, node_embedding)
        except KeyError:
            # If it's node embedding Cannot exist, give default low score
            relevance_out[node.node_id] = 0.0
        except Exception as e:
            print(f"Calculate Nodes {node.node_id} Error while correlation: {e}")
            relevance_out[node.node_id] = 0.0

    return relevance_out

async def further_retrieve_personalized(student, focus_text, focus_embedding, base_n_count=10):
    """
    Personalized Memory Retrieval Function
    INPUT:
        student: Student Category
        focus_text: str, Focus Text
        focus_embedding: list, Projected embedding Vector
        base_n_count: int, Number of basic searches
    OUTPUT:
        master_nodes: list, Personalized ConceptNode Examples List
    """
    # Get personalized parameters
    params = student.get_personalized_retrieval_params()
    n_count = params["n_count"]

    print(f"[Search] {student.name} Individualized parameters: Number={n_count}, Relevance weights={params['relevance_weight']:.1f}")

    # Fetch All Memory Nodes
    nodes = [[i.last_accessed, i] for i in student.mem.seq_thought + student.mem.seq_knowledge]

    if not nodes:
        print(f"Students {student.name} No memory")
        return []

    # Sort by Time
    nodes.sort(key=lambda x: x[0], reverse=True)
    nodes = [i[1] for i in nodes]

    # Calculate the dimensions fractions (using individualized weights)）
    recency_out = extract_recency(student, nodes)
    recency_out = normalize_dict_floats(recency_out, 0, 1)

    importance_out = extract_importance(student, nodes)
    importance_out = normalize_dict_floats(importance_out, 0, 1)

    relevance_out = extract_relevance_with_precomputed_embedding(
        student, nodes, focus_embedding
    )
    relevance_out = normalize_dict_floats(relevance_out, 0, 1)

    # Apply similarity threshold filter
    similarity_threshold = params["similarity_threshold"]
    filtered_relevance = {k: v for k, v in relevance_out.items()
                         if v >= similarity_threshold}

    if not filtered_relevance:
        print(f"[Search] {student.name} No similarities found ≥ {similarity_threshold} The memory, lower the threshold")
        similarity_threshold = 0.05
        filtered_relevance = {k: v for k, v in relevance_out.items()
                             if v >= similarity_threshold}

    # Use personalized weights for a comprehensive rating
    master_out = dict()
    for key in filtered_relevance.keys():
        if key in recency_out and key in importance_out:
            master_out[key] = (
                params["recency_weight"] * recency_out[key] * student.scratch.recency_w +
                params["importance_weight"] * importance_out[key] * student.scratch.importance_w +
                params["relevance_weight"] * relevance_out[key] * student.scratch.relevance_w
            )

    if not master_out:
        print(f"[Search] {student.name} I didn't find a proper memory")
        return []

    # Diversity treatment (if required)）
    diversity_factor = params["diversity_factor"]
    if diversity_factor > 0:
        master_out = apply_diversity_penalty(student, master_out, diversity_factor)

    # Selection top-N
    master_out = top_x_values(master_out, n_count)
    master_nodes = [student.mem.id_to_node[i] for i in list(master_out.keys())]

    # Update access time
    for node in master_nodes:
        node.last_accessed = student.scratch.current_time

    print(f"[Search] {student.name} Finally retrieved {len(master_nodes)} A memory")
    return master_nodes

def apply_diversity_penalty(student, master_out, diversity_factor):
    """
    Apply diversity penalties to avoid retrieving memories that are too similar
    """
    if diversity_factor <= 0:
        return master_out

    # Simple diversity strategy: punitive memory of overlapping keywords
    diverse_out = master_out.copy()
    selected_keywords = set()

    for node_id in sorted(master_out.keys(), key=lambda x: master_out[x], reverse=True):
        try:
            node = student.mem.id_to_node[node_id]
            node_keywords = set(getattr(node, 'keywords', []))

            # Calculating overlaps with selected key words
            overlap = len(node_keywords & selected_keywords)
            penalty = diversity_factor * overlap

            diverse_out[node_id] = max(0, diverse_out[node_id] - penalty)
            selected_keywords.update(node_keywords)

        except Exception:
            continue

    return diverse_out