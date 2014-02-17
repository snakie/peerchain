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
        block["stakeage"] = format(block["stakeage"],'.2f')
        block["time"] = block["time"].strftime("%Y-%m-%d %H:%M:%S+0000")
        return block
    def stats_to_json(self,stattuple):
        stats = stattuple._asdict()
        stats["mined_coins"] = format(stats["mined_coins"] / 1e6,'.6f')
        stats["minted_coins"] = format(stats["minted_coins"] / 1e6,'.6f')
        stats["money_supply"] = format(stats["money_supply"] / 1e6,'.6f')
        stats["destroyed_fees"] = format(stats["destroyed_fees"] / 1e6,'.6f')
        stats["time"] = stats["time"].strftime("%Y-%m-%d %H:%M:%S+0000")
        return stats
    #def compare_stats(self,firsttuple,secondtuple):
    def compare_stats(self,firsttuple,secondtuple):
        if firsttuple == 'stats not found':
            return "error, unable to find stats for first id"
        if secondtuple == 'stats not found':
            return "error, unable to find stats for second id"
        #print firsttuple
        #print secondtuple
        first = firsttuple._asdict()
        second = secondtuple._asdict()
        ret = {}
        ret['last_block'] = first['last_block']
        ret['first_block'] = second['last_block']
        ret['block_delta'] = first['last_block'] - second['last_block']
        ret['pos_blocks'] = first['pos_blocks'] - second['pos_blocks']
        ret['pow_blocks'] = first['pow_blocks'] - second['pow_blocks']
        ret['transactions'] = first['transactions'] - second['transactions']
        ret['duration'] = first['time'] - second['time']
        ret["inflation_rate"] = (first["money_supply"] - second["money_supply"]) / 1e6
        ret["money_supply_delta"] = format(ret["inflation_rate"],'.6f')
        total_seconds = ret['duration'].days * 86400 + ret['duration'].seconds
        print total_seconds
        times_in_year = 31536000 / total_seconds
        print times_in_year
        print
        ret['inflation_rate'] = format(100*ret['inflation_rate'] * times_in_year / (first['money_supply']/1e6),'.2f')
        ret['duration'] = ret['duration'].__str__()
        ret["money_supply_end"] = format(first["money_supply"] / 1e6,'.6f')
        ret["mined_coins"] = format((first["mined_coins"]-second["mined_coins"]) / 1e6,'.6f')
        ret["minted_coins"] = format((first["minted_coins"]-second["minted_coins"]) / 1e6,'.6f')
        ret["destroyed_fees"] = format((first["destroyed_fees"]-second["destroyed_fees"]) / 1e6,'.6f')
        #print first
        return json.dumps(ret)
    def get_stats(self,id,pretty=True):
        future = self.session.execute_async(self.stat_query, dict(id=id))
        try:
            rows = future.result()
        except Exception as e:
            return str(e)
        if len(rows) == 0:
            return "stats not found"
        stats = rows[0]
        if pretty:
            return self.stats_to_json(stats)
        return stats
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
            return json.dumps(self.blockchain.get_stats(id))
        return "block height too large"

class CompareLastStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, delta):
        try:
            delta = int(delta)
        except ValueError:
            return "delta must be a number"
        last = self.blockchain.get_block_count() - 1
        if delta > last:
            return "delta must be less then total block height"
        first_stats = self.blockchain.get_stats(last,False)
        second_stats = self.blockchain.get_stats(last-delta,False)
        return blockchain.compare_stats(first_stats,second_stats)

class CompareDeltaStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, first, delta):
        try:
            first = int(first)
            delta = int(delta)
        except ValueError:
            return "block id and delta must be numbers"
        if delta > first:
            return "delta must be less then total block height"
        first_stats = self.blockchain.get_stats(first,False)
        second_stats = self.blockchain.get_stats(first-delta,False)
        return blockchain.compare_stats(first_stats,second_stats)

class CompareStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, first, second):
        try:
            first = int(first)
            second = int(second)
        except ValueError:
            return "first and second block ids must be numbers"
        if second > first:
            return "first id must be greater then second id"
        first_stats = self.blockchain.get_stats(first,False)
        second_stats = self.blockchain.get_stats(second,False)
        return blockchain.compare_stats(first_stats,second_stats)

class LastStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, count=None):
        if count == None:
            count = 1
            id = self.blockchain.get_block_count() - 1
            return json.dumps(self.blockchain.get_stats(id))
        try:
            count = int(count)
        except ValueError:
            return "count must be a number"
        if count > 10:
            return "count cannot be greater then 10"
        last_id = self.blockchain.get_block_count() - 1
        data = { 'last' : last_id }
        network = []
        for c in range(count):
            curr = last_id-c
            network.append(self.blockchain.get_stats(curr))
        data['data'] = network;
        return json.dumps(data);

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
    network/last/&lt;n&gt; - fetch last n network statistics

    compare/&lt;first_id&gt;/&lt;second_id&gt; - compare network stats for two block heights
    compare/delta/&lt;id&gt;/&lt;delta&gt; - compare network stats for a block 'id' and block 'id-delta'
    compare/last/&lt;delta&gt; - compare last block and 'last block - delta' network stats
    
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

api.compare = CompareStats(blockchain)
api.compare.delta = CompareDeltaStats(blockchain)
api.compare.last = CompareLastStats(blockchain)

config = {'/':
    {
        'request.dispatch' : cherrypy.dispatch.MethodDispatcher()
    }
}
application = cherrypy.tree.mount(api,"/api",config)
cherrypy.config.update({'error_page.404': error_404, 
                 #       'environment':'production',
                        'log.error_file': '/app/logs/api_server.error.log',
                        'log.access_file': '/app/logs/api_server.access.log'})

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

