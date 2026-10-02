import json
import sys

import aiofiles

from datetime import datetime

sys.path.append("../")

from student.global_methods import *

class ConceptNode:
    def __init__(self,
                 node_id, node_count, type_count, node_type, depth,
                 created, expiration,
                content, embedding_key, importance, keywords, event_type=None, s=None, p=None, o=None, knowledge_tag=None, theme=None, misconceptions=None):
        self.node_id = node_id
        self.node_count = node_count
        self.type_count = type_count
        self.type = node_type
        self.depth = depth

        self.created = created
        self.expiration = expiration
        self.last_accessed = self.created

        # self.description = description
        self.content = content
        self.embedding_key = embedding_key
        self.importance = importance
        # The key words here should be(s, p, o, knowledge_tag)Composition
        # The first three are in node_type Yes event, chat, thought It happens
        # The last one is here node_type Yes knowledge, thought It happens
        # But thought Are there two possible types? Thinking about knowledge points, and thinking about events, dialogues; different situations may have to be sorted out？
        self.keywords = keywords
        # self.filling = filling

        self.event_type = event_type
        self.s = s
        self.p = p
        self.o = o
        self.knowledge_tag = knowledge_tag # Label for storing knowledge(list)
        self.theme = theme # Theme used to store events(list)

        self.misconceptions = misconceptions  # List of misunderstandings or errors associated with the node(Knowledge Node)


class Memory:
    def __init__(self, f_saved):
        self.id_to_node = dict()

        # It's always plugged into the head to keep the memory sequence
        # and available `retention` Parameters to control their forgotten factor
        # So every memory we can remember is new retention individual
        # So just get it 0——retention - 1 Just memory
        self.seq_event = []
        self.seq_thought = []
        self.seq_chat = []
        self.seq_knowledge = []

        self.kw_to_event = dict()
        self.kw_to_thought = dict()
        self.kw_to_chat = dict()
        self.kw_to_knowledge = dict()

        # Whenever a new event or reflection is added to the memory, the code goes through the key word associated with it and adds the number of the keyword to the corresponding dictionary。
        self.kw_strength_event = dict()
        self.kw_strength_thought = dict()

        # embeddings It's a dictionary. It's for memory nodes content, Value corresponds to embedding Vector
        embeddings_file_path = f_saved + "/embeddings.json"
        with open(embeddings_file_path, 'r', encoding='utf-8') as f:
            self.embeddings = json.load(f)


        nodes_file_path = f_saved + "/nodes.json"
        with open(nodes_file_path, 'r', encoding='utf-8') as f:
            nodes_load = json.load(f)
        for cnt in range(len(nodes_load.keys())):
            node_id = f"node_{str(cnt+1)}"
            node_details = nodes_load[node_id]

            node_count = node_details["node_count"]
            type_count = node_details["type_count"]
            node_type = node_details["type"]
            depth = node_details["depth"]

            # created = datetime.datetime.strptime(node_details["created"], "%Y-%m-%d %H:%M:%S")
            created = datetime.strptime(node_details["created"], "%Y-%m-%d %H:%M:%S")

            expiration = None
            if node_details["expiration"]:
                # expiration = datetime.datetime.strptime(node_details["expiration"], "%Y-%m-%d %H:%M:%S")
                expiration = datetime.strptime(node_details["expiration"], "%Y-%m-%d %H:%M:%S")

            """s = node_details["s"]
            p = node_details["p"]
            o = node_details["o"]

            knowledge_tag = node_details["knowledge_tag"]
            event_type = node_details["event_type"]"""

            # The variables here may not exist and need to be used get Method of acquisition
            event_type = node_details.get("event_type", None)
            theme = node_details.get("theme", None)
            knowledge_tag = node_details.get("knowledge_tag", None)


            # description = node_details["description"]
            content = node_details["content"]
            embedding_pair = (node_details["embedding_key"], self.embeddings[node_details["embedding_key"]])
            importance = node_details["importance"]
            keywords = node_details["keywords"]
            misconceptions = node_details.get("misconceptions", None)


            if node_type == "event":
                self.add_event(created, content, keywords, importance,
                                embedding_pair, event_type, theme)
            elif node_type == "thought":
                self.add_thought(created,
                                content, keywords, importance,
                                embedding_pair)
            elif node_type == "chat":
                self.add_chat(created,
                                content, keywords, importance,
                                embedding_pair)
            elif node_type == "knowledge":
                self.add_knowledge(created,
                                    content, keywords, importance,
                                    embedding_pair, knowledge_tag, misconceptions=misconceptions)

    def save(self, out_json):
        r = dict()
        for cnt in range(len(self.id_to_node.keys())):
            node_id = f"node_{str(cnt+1)}"
            node = self.id_to_node[node_id]

            r[node_id] = dict()
            r[node_id]["node_count"] = node.node_count
            r[node_id]["type_count"] = node.type_count
            r[node_id]["type"] = node.type
            r[node_id]["depth"] = node.depth

            r[node_id]["created"] = node.created.strftime("%Y-%m-%d %H:%M:%S")
            if node.expiration:
                r[node_id]["expiration"] = node.expiration.strftime("%Y-%m-%d %H:%M:%S")
            else:
                r[node_id]["expiration"] = None

            r[node_id]["s"] = node.s
            r[node_id]["p"] = node.p
            r[node_id]["o"] = node.o

            r[node_id]["knowledge_tag"] = node.knowledge_tag
            r[node_id]["event_type"] = node.event_type
            # r[node_id]["description"] = node.description
            r[node_id]["content"] = node.content
            r[node_id]["embedding_key"] = node.embedding_key
            r[node_id]["importance"] = node.importance
            r[node_id]["keywords"] = node.keywords
            r[node_id]["misconceptions"] = node.misconceptions

        with open(out_json + "/nodes.json", "w", encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=4)

        with open(out_json+"/embeddings.json", "w", encoding='utf-8') as outfile:
            json.dump(self.embeddings, outfile, ensure_ascii=False, indent=4)

    async def save_async(self, out_json):
        r = dict()
        for cnt in range(len(self.id_to_node.keys())):
            node_id = f"node_{str(cnt+1)}"
            node = self.id_to_node[node_id]

            r[node_id] = dict()
            r[node_id]["node_count"] = node.node_count
            r[node_id]["type_count"] = node.type_count
            r[node_id]["type"] = node.type
            r[node_id]["depth"] = node.depth

            r[node_id]["created"] = node.created.strftime("%Y-%m-%d %H:%M:%S")
            if node.expiration:
                r[node_id]["expiration"] = node.expiration.strftime("%Y-%m-%d %H:%M:%S")
            else:
                r[node_id]["expiration"] = None

            r[node_id]["s"] = node.s
            r[node_id]["p"] = node.p
            r[node_id]["o"] = node.o

            r[node_id]["knowledge_tag"] = node.knowledge_tag
            r[node_id]["event_type"] = node.event_type
            # r[node_id]["description"] = node.description
            r[node_id]["content"] = node.content
            r[node_id]["embedding_key"] = node.embedding_key
            r[node_id]["importance"] = node.importance
            r[node_id]["keywords"] = node.keywords
            r[node_id]["misconceptions"] = node.misconceptions

        async with aiofiles.open(out_json + "/nodes.json", "w", encoding='utf-8') as f:
            await f.write(json.dump(r, f, ensure_ascii=False, indent=4))

        async with aiofiles.open(out_json+"/embeddings.json", "w", encoding='utf-8') as outfile:
            await f.write(json.dump(self.embeddings, outfile, ensure_ascii=False, indent=4))



    # Events keywords It should be the type of event+Theme
    # embedding_pair It's a metagroup, including event.content And the corresponding embedding Vector
    def add_event(self, created, content, keywords, importance,
                   embedding_pair, event_type, theme,
                   expiration = None, s = None, p = None, o = None):
        """
        Save Event。
        """
        node_count = len(self.id_to_node.keys()) + 1
        type_count = len(self.seq_event) + 1
        node_type = "event"
        node_id = f"node_{str(node_count)}"
        depth = 0

        node = ConceptNode(node_id, node_count, type_count, node_type, depth,
                           created, expiration,
                           content, embedding_pair[0],
                            importance, keywords, event_type=event_type, theme=theme, s=s, p=p, o=o)

        # Insert Head
        self.seq_event.insert(0, node)
        keywords = [i for i in keywords if i]  # Remove empty keyword
        for kw in keywords:
            if kw in self.kw_to_event:
                self.kw_to_event[kw][0:0] = [node]
            else:
                self.kw_to_event[kw] = [node]
        self.id_to_node[node_id] = node

        self.embeddings[embedding_pair[0]] = embedding_pair[1]

        return node

    def add_thought(self, created, content, keywords, importance,
                     embedding_pair,
                     expiration = None, s = None, p = None, o = None):
        """
        Save thought。
        """
        node_count = len(self.id_to_node.keys()) + 1
        type_count = len(self.seq_thought) + 1
        node_type = "thought"
        node_id = f"node_{str(node_count)}"
        depth = 1

        node = ConceptNode(node_id, node_count, type_count, node_type, depth,
                            created, expiration,
                            content, embedding_pair[0],
                            importance, keywords, s=s, p=p, o=o)
        # Insert Head
        self.seq_thought.insert(0, node)
        keywords = [i for i in keywords if i]
        for kw in keywords:
            if kw in self.kw_to_thought:
                self.kw_to_thought[kw][0:0] = [node]
            else:
                self.kw_to_thought[kw] = [node]
        self.id_to_node[node_id] = node

        self.embeddings[embedding_pair[0]] = embedding_pair[1]
        return node

    def add_chat(self, created, content, keywords, importance,
                     embedding_pair,
                     expiration = None, s = None, p = None, o = None, knowledge_tag = None):
        """
        Save Dialogue。
        """
        node_count = len(self.id_to_node.keys()) + 1
        type_count = len(self.seq_chat) + 1
        node_type = "chat"
        node_id = f"node_{str(node_count)}"
        depth = 0

        node = ConceptNode(node_id, node_count, type_count, node_type, depth,
                            created, expiration,
                            content, embedding_pair[0],
                            importance, keywords, s=s, p=p, o=o, knowledge_tag=knowledge_tag)
        # Insert Head
        self.seq_chat.insert(0, node)
        keywords = [i for i in keywords if i]
        for kw in keywords:
            if kw in self.kw_to_chat:
                self.kw_to_chat[kw][0:0] = [node]
            else:
                self.kw_to_chat[kw] = [node]
        self.id_to_node[node_id] = node

        self.embeddings[embedding_pair[0]] = embedding_pair[1]

        return node

    def add_knowledge(self, created, content, keywords, importance,
                      embedding_pair, knowledge_tag, misconceptions=None,
                     expiration = None):
        """
        Preservation of knowledge。
        """
        node_count = len(self.id_to_node.keys()) + 1
        type_count = len(self.seq_knowledge) + 1
        node_type = "knowledge"
        node_id = f"node_{str(node_count)}"
        depth = 0
        node = ConceptNode(node_id, node_count, type_count, node_type, depth,
                            created, expiration,
                            content, embedding_pair[0],
                            importance, keywords, knowledge_tag=knowledge_tag, misconceptions=misconceptions)

        # Insert Head
        self.seq_knowledge.insert(0, node)
        keywords = [i for i in keywords if i]
        for kw in keywords:
            if kw in self.kw_to_knowledge:
                self.kw_to_knowledge[kw][0:0] = [node]
            else:
                self.kw_to_knowledge[kw] = [node]
        self.id_to_node[node_id] = node
        self.embeddings[embedding_pair[0]] = embedding_pair[1]
        return node


    def retrieve_relevant_thoughts(self, keywords):
        """
        Retrieving ideas related to given keywords。
        """
        relevant_thoughts = []
        for kw in keywords:
            if kw in self.kw_to_thought:
                relevant_thoughts.extend(self.kw_to_thought[kw])

        # Go and keep order (if necessary, but set It'll mess up the order）
        # If you need to keep the insertion order heavy, you can use OrderedDict Or something
        # It's simple here set Go heavy and turn around list
        # Note: If ConceptNode Object cannot be Hashi. Use it directly set It's a mistake. We need to make sure ConceptNode But Hashi or store it id
        # Assumptions ConceptNode Yes id It's the only one and the only one
        # relevant_thoughts = list(set(relevant_thoughts))
        # A safer approach is based on node_id Heavy
        seen_ids = set()
        unique_thoughts = []
        for thought_node in relevant_thoughts:
            if thought_node.node_id not in seen_ids:
                unique_thoughts.append(thought_node)
                seen_ids.add(thought_node.node_id)
        return unique_thoughts

    def retrieve_relevant_knowledge(self, keywords):
        """
        Retrieving knowledge related to given keywords。
        """
        relevant_knowledge = []
        for kw in keywords:
            if kw in self.kw_to_knowledge:
                relevant_knowledge.extend(self.kw_to_knowledge[kw])

        seen_ids = set()
        unique_knowledge = []
        for knowledge_node in relevant_knowledge:
            if knowledge_node.node_id not in seen_ids:
                unique_knowledge.append(knowledge_node)
                seen_ids.add(knowledge_node.node_id)
        return unique_knowledge

