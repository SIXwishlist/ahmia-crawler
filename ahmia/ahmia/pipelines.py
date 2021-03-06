# -*- coding: utf-8 -*-
"""
In this module, you can find pipelines.
AnchorTextPipeline is responsible to index an anchor text with the target
document.
AuthorityPipeline stores links until the spider is closed. Then it creates a
graph and compute the pagerank algorithm on it.
"""
from datetime import datetime
import hashlib
from urlparse import urlparse

from scrapyelasticsearch.scrapyelasticsearch import ElasticSearchPipeline

from .items import DocumentItem, LinkItem, AuthorityItem

class CustomElasticSearchPipeline(ElasticSearchPipeline):
    """
    CustomElasticSearchPipeline is responsible to index items to ES.
    In this version, the index_item method is different because to it needs to
    handle different type of items.
    """
    items_buffer = []

    def index_item(self, item):
        """
        Item are indexed here.
        This method receives an item which can be of type DocumentItem,
        LinkItem or AuthorityItem.
        Note: You should add the following line to your elasticsearch.yml file
        script.engine.groovy.inline.update: on
        """
        index_name = self.settings['ELASTICSEARCH_INDEX']
        index_suffix_format = self.settings.get(
            'ELASTICSEARCH_INDEX_DATE_FORMAT', None)

        if index_suffix_format:
            index_name += "-" + datetime.strftime(datetime.now(),
                                                  index_suffix_format)

        if isinstance(item, DocumentItem):
            index_action = {
                '_index': index_name,
                '_type': self.settings['ELASTICSEARCH_TYPE'],
                '_id': hashlib.sha1(item['url']).hexdigest(),
                '_source': dict(item)
            }
        elif isinstance(item, LinkItem):
            index_action = {
                "_op_type": "update",
                "_index": index_name,
                "_type": self.settings['ELASTICSEARCH_TYPE'],
                "_id": hashlib.sha1(item['target']).hexdigest(),
                "script": {
                    "inline": """ctx._source.anchors = ctx._source.anchors ?
                              (ctx._source.anchors + [anchor]).unique{it}
                              : [anchor]""",
                    "params" : {
                        "anchor" : item["anchor"]
                    }
                },
                "upsert": {
                    "anchors": [item["anchor"]],
                    "url": item['target'],
                    "domain": urlparse(item['target']).hostname,
                    "updated_on": datetime.now().strftime(
                        "%Y-%m-%dT%H:%M:%S")
                }
            }
        elif isinstance(item, AuthorityItem):
            index_action = {
                "_op_type": "update",
                "_index": index_name,
                "_type": self.settings['ELASTICSEARCH_TYPE'],
                "_id": item['url'],
                "doc": {
                    "authority": item['score']
                }
            }
        else:
            return

        self.items_buffer.append(index_action)

        if len(self.items_buffer) >= \
          self.settings.get('ELASTICSEARCH_BUFFER_LENGTH', 500):
            self.send_items()
            self.items_buffer = []
