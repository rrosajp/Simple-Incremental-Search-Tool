import json
import os
import elasticsearch
import requests
from elasticsearch import helpers


class Search:

    def __init__(self, index: str):
        self.index_name = index
        self.es = elasticsearch.Elasticsearch()

        try:
            requests.head("http://localhost:9200")
            print("elasticsearch is already running")
        except:
            print("elasticsearch is not running")

        self.search_iterator = None

    def get_all_documents(self, dir_id: int):

        return helpers.scan(client=self.es,
                            query={"_source": {"includes": ["path", "name", "mime", "extension"]},
                                   "query": {"term": {"directory": dir_id}}},
                            index=self.index_name)

    def get_index_size(self):

        try:
            info = requests.get("http://localhost:9200/" + self.index_name + "/_stats")

            if info.status_code == 200:

                parsed_info = json.loads(info.text)

                return int(parsed_info["indices"][self.index_name]["primaries"]["store"]["size_in_bytes"])
        except:
            return 0

    def get_doc_count(self):

        try:
            info = requests.get("http://localhost:9200/" + self.index_name + "/_stats")

            if info.status_code == 200:
                parsed_info = json.loads(info.text)

                return int(parsed_info["indices"][self.index_name]["primaries"]["indexing"]["index_total"])
        except:
            return 0

    def get_mime_types(self):

        query = self.es.search(body={
            "aggs": {
                "mimeTypes": {
                    "terms": {
                        "field": "mime_kw",
                        "size": 10000
                    }
                }
            }
        })

        return query["aggregations"]["mimeTypes"]["buckets"]

    def get_mime_map(self):

        mime_map = []

        for mime in self.get_mime_types():
            splited_mime = os.path.split(mime["key"])

            child = dict()
            child["text"] = splited_mime[1] + " (" + str(mime["doc_count"]) + ")"
            child["id"] = mime["key"]

            mime_category_exists = False

            for category in mime_map:
                if category["text"] == splited_mime[0]:
                    category["children"].append(child)
                    mime_category_exists = True
                    break

            if not mime_category_exists:
                mime_map.append({"text": splited_mime[0], "children": [child]})

        return mime_map

    def search(self, query, size_min, size_max, mime_types, must_match, directories, path):

        condition = "must" if must_match else "should"
        print(directories)

        filters = [
            {"range": {"size": {"gte": size_min, "lte": size_max}}},
            {"terms": {"directory": directories}}
        ]

        if path != "":
            filters.append({"term": {"path": path}})

        if mime_types != "any":
            filters.append({"terms": {"mime": mime_types}})

        page = self.es.search(body={
            "query": {
                "bool": {
                    condition: {
                        "multi_match": {
                            "query": query,
                            "fields": ["name", "content", "album", "artist", "title", "genre",
                                       "album_artist", "font_name"],
                            "operator": "and"
                        }
                    },
                    "filter": filters
                }
            },
            "sort": [
                "_score"
            ],
            "highlight": {
                "fields": {
                    "content": {"pre_tags": ["<span class='hl'>"], "post_tags": ["</span>"]},
                    "name": {"pre_tags": ["<span class='hl'>"], "post_tags": ["</span>"]},
                    "font_name": {"pre_tags": ["<span class='hl'>"], "post_tags": ["</span>"]},
                }
            },
            "aggs": {
                "total_size": {"sum": {"field": "size"}}
            },
            "size": 40}, index=self.index_name, scroll="3m")

        return page

    def suggest(self, prefix):

        suggestions = self.es.search(body={
            "suggest": {
                "path": {
                    "prefix": prefix,
                    "completion": {
                        "field": "suggest-path",
                        "skip_duplicates": True,
                        "size": 10000
                    }
                }
            }
        })

        path_list = []

        for option in suggestions["suggest"]["path"][0]["options"]:
            path_list.append(option["_source"]["path"])

        return path_list

    def scroll(self, scroll_id):

        page = self.es.scroll(scroll_id=scroll_id, scroll="3m")

        return page

    def get_doc(self, doc_id):

        try:
            return self.es.get(index=self.index_name, id=doc_id, doc_type="file")
        except elasticsearch.exceptions.NotFoundError:
            return None
