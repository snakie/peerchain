#!/usr/local/bin/python

import sys
sys.stdout = sys.stderr

import atexit
import threading
import cherrypy, json
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement

if __name__ != '__main__':
    cherrypy.config.update({'environment':'embedded'})
    if cherrypy.engine.state == 0:
        cherrypy.engine.start(blocking=False)
        atexit.register(cherrypy.engine.stop)

class Blockchain(object):
    def __init__(self,host='127.0.0.1',keyspace='peerchain'):
        self.cluster = Cluster([host]) 
        self.session = self.cluster.connect()
        self.session.set_keyspace(keyspace)
        self.block_query = SimpleStatement("SELECT * from blocks where id=%(id)s")
        self.stat_query = SimpleStatement("SELECT * from stats where last_block=%(id)s")
        self.last_query = SimpleStatement("SELECT value from counters where name='blocks'")
    def block_to_json(self,blocktuple):
        block = blocktuple._asdict()
        block["staked"] = format(block["staked"] / 1e6,'.6f')
        block["diff"] = format(block["diff"],'.8f')
        block["reward"] = format(block["reward"] / 1e6,'.6f')
        block["sent"] = format(block["sent"] / 1e6,'.6f')
        block["received"] = format(block["received"] / 1e6,'.6f')
        block["destroyed"] = format(block["destroyed"] / 1e6,'.6f')
        block["time"] = block["time"].strftime("%Y-%m-%d %H:%M:%S+0000")
        return block
    def stats_to_json(self,stattuple):
        stats = stattuple._asdict()
        stats["mined_coins"] = format(stats["mined_coins"] / 1e6,'.6f')
        stats["minted_coins"] = format(stats["minted_coins"] / 1e6,'.6f')
        stats["money_supply"] = format(stats["money_supply"] / 1e6,'.6f')
        stats["destroyed_fees"] = format(stats["destroyed_fees"] / 1e6,'.6f')
        stats["time"] = stats["time"].strftime("%Y-%m-%d %H:%M:%S")
        return stats
    def get_stats(self,id):
        future = self.session.execute_async(self.stat_query, dict(id=id))
        try:
            rows = future.result()
        except Exception as e:
            return str(e)
        if len(rows) == 0:
            return "stats not found"
        stats = rows[0]
        return json.dumps(self.stats_to_json(stats))
    def get_block(self,block_id,tojson=True):
        try:
            id = int(block_id)
        except ValueError:
            return "block id must be a number"
        future = self.session.execute_async(self.block_query, dict(id=id))
        try:
            rows = future.result()
        except Exception as e:
            return str(e)
        if len(rows) == 0:
            return "block not found"
        block = rows[0]
        if tojson:
            return json.dumps(self.block_to_json(block))
        return self.block_to_json(block)
            
    def get_block_count(self):
        future = self.session.execute_async(self.last_query)
        try:
            rows = future.result()
        except Exception as e:
            return str(e)
        if len(rows) == 0:
            return "failed to fetch last block count"
        value = rows[0][0]
        return value



class Blocks(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, id=None):
        if id == None:
            return "Add a block number or the keyword last to the url: blocks/86754"
        try:
            id = int(id)
        except ValueError:
            return "block id must be a number"
        if id < 10000000:
            return self.blockchain.get_block(id)
        return "block id too large"

class LastBlock(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, count=None):
        if count == None:
            count = 1
            last_id = self.blockchain.get_block_count() - 1
            return self.blockchain.get_block(last_id)
        try:
            count = int(count)
        except ValueError:
            return "count must be a number"
        if count > 10:
            return "count cannot be greater then 10"
        last_id = self.blockchain.get_block_count() - 1
        data = { 'last' : last_id }
        blocks = []
        for c in range(count):
            curr = last_id-c
            blocks.append(self.blockchain.get_block(curr,False))
        data['blocks'] = blocks;
        return json.dumps(data)

class Stats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, id=None):
        if id == None:
            return "Add a block number to the url: network/86754"
        try:
            id = int(id)
        except ValueError:
            return "block height must be a number"
        if id < 10000000:
            return self.blockchain.get_stats(id)
        return "block height too large"

class LastStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self):
        id = self.blockchain.get_block_count() - 1
        return self.blockchain.get_stats(id)

class BlockCount(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self):
        return json.dumps(self.blockchain.get_block_count() - 1)

class Index(object):
    exposed = True
    def GET(self):
        usage = """<pre>
  peercoin blockchain json api
    by snakie (snakie at yahoo.com)
    donations: PGiNfS4KTmb7W9GDxrA54tYTRhmSK36Pyj<br>
        
  supported methods:
    blocks/count - fetch total block count
    blocks/&lt;id&gt; - fetch block meta data
    blocks/last - fetch last block
    blocks/last/&lt;n&gt; - fetch last n blocks
    network/&lt;id&gt;  - fetch network statistics at a block number
    network/last - fetch last block
        </pre>""";
        return usage
    def default(self):
        return "method not implemented"

def error_404(status,message,traceback,version):
    return "method not implemented"

api = Index()
blockchain = Blockchain()

api.blocks = Blocks(blockchain)
api.blocks.last = LastBlock(blockchain)
api.blocks.count = BlockCount(blockchain)

api.network = Stats(blockchain)
api.network.last = LastStats(blockchain)

config = {'/':
    {
        'request.dispatch' : cherrypy.dispatch.MethodDispatcher()
    }
}
application = cherrypy.tree.mount(api,"/api",config)
cherrypy.config.update({'error_page.404': error_404})

if __name__ == '__main__':
    #cherrypy.quickstart(application)
    cherrypy.server.unsubscribe()
    server = cherrypy._cpserver.Server()
    server.socket_host = "0.0.0.0"
    server.socket_port = 8081
    server.thread_pool = 30
    server.subscribe()
    cherrypy.engine.start() 
    cherrypy.engine.block()

