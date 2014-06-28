#!/usr/local/bin/python

import sys
sys.stdout = sys.stderr

import atexit
import threading
import cherrypy, json
import datetime
import sqlite3

if __name__ != '__main__':
    cherrypy.config.update({'environment':'embedded'})
    if cherrypy.engine.state == 0:
        cherrypy.engine.start(blocking=False)
        atexit.register(cherrypy.engine.stop)

database=None
database_path='/app/var/peerchain.db'
database=threading.local()

def connect(thread_index):
    global database,database_path
    #print "connect called thread: "+str(thread_index)
    database.conn = sqlite3.connect(database_path)
    database.conn.row_factory = sqlite3.Row

class Blockchain(object):
    def __init__(self,file='/app/var/peerchain.db'):
        #self.conn = sqlite3.connect(file, check_same_thread=False);
        #self.conn.row_factory = sqlite3.Row
        #self.cursor = self.conn.cursor();
        #global database
        #self.local = threading.local()
        #self.local.cursor = database.conn.cursor()
        self.block_query = "SELECT * from blocks where id=?"
        self.stat_query = "SELECT * from stats where last_block=?"
        self.last_query = "SELECT max(id) from blocks"
    def block_to_json(self,block):
        block["staked"] = format(block["staked"] / 1e6,'.6f')
        block["diff"] = format(block["diff"],'.8f')
        block["reward"] = format(block["reward"] / 1e6,'.6f')
        block["sent"] = format(block["sent"] / 1e6,'.6f')
        block["POS"] = block["POS"].lower()
        block["received"] = format(block["received"] / 1e6,'.6f')
        block["destroyed"] = format(block["destroyed"] / 1e6,'.6f')
        block["stakeage"] = format(block["stakeage"],'.2f')
        block["time"] = datetime.datetime.utcfromtimestamp(block["time"] / 1e3).strftime("%Y-%m-%d %H:%M:%S+0000")
        return block
    def stats_to_json(self,stats):
        stats["mined_coins"] = format(stats["mined_coins"] / 1e6,'.6f')
        stats["minted_coins"] = format(stats["minted_coins"] / 1e6,'.6f')
        stats["money_supply"] = format(stats["money_supply"] / 1e6,'.6f')
        stats["destroyed_fees"] = format(stats["destroyed_fees"] / 1e6,'.6f')
        stats["time"] = datetime.datetime.utcfromtimestamp(stats["time"] / 1e3).strftime("%Y-%m-%d %H:%M:%S+0000")
        return stats
    def rowtodict(self,tuple):
        dict = {}
        for key in tuple.keys():
            dict[key] = tuple[key]
        return dict
    #def compare_stats(self,firsttuple,secondtuple):
    def compare_stats(self,first,second):
        if first == 'stats not found':
            return "error, unable to find stats for first id"
        if second == 'stats not found':
            return "error, unable to find stats for second id"
        #print firsttuple
        #print secondtuple
        ret = {}
        ret['last_block'] = first['last_block']
        ret['first_block'] = second['last_block']
        ret['block_delta'] = first['last_block'] - second['last_block']
        ret['pos_blocks'] = first['POS_blocks'] - second['POS_blocks']
        ret['pow_blocks'] = first['POW_blocks'] - second['POW_blocks']
        ret['transactions'] = first['transactions'] - second['transactions']
        total_seconds = (first['time'] - second['time']) / 1e3
        ret['duration'] = datetime.timedelta(0,total_seconds)
        #ret['duration'] = first['time'] - second['time']
        ret["inflation_rate"] = (first["money_supply"] - second["money_supply"]) / 1e6
        ret["money_supply_delta"] = format(ret["inflation_rate"],'.6f')
        #total_seconds = ret['duration'] / 1e3
        times_in_year = 31536000 / float(total_seconds)
        ret['inflation_rate'] = format(100*ret['inflation_rate'] * times_in_year / (first['money_supply']/1e6),'.2f')
        ret['duration'] = ret['duration'].__str__()
        ret["money_supply_end"] = format(first["money_supply"] / 1e6,'.6f')
        ret["mined_coins"] = format((first["mined_coins"]-second["mined_coins"]) / 1e6,'.6f')
        ret["minted_coins"] = format((first["minted_coins"]-second["minted_coins"]) / 1e6,'.6f')
        ret["destroyed_fees"] = format((first["destroyed_fees"]-second["destroyed_fees"]) / 1e6,'.6f')
        #print first
        return json.dumps(ret)
    def get_stats(self,id,pretty=True):
        global database
        cursor = database.conn.cursor()
        query = cursor.execute(self.stat_query,(id,))
        stats = cursor.fetchone()
        if stats is None:
            print "stats "+id+" not found"
            return "stats not found"
        stats = self.rowtodict(stats)
        if pretty:
            return self.stats_to_json(stats)
        return stats
    def get_series_stats(self,type,id):
        if type == 'diff': #diff is in the blocks table
            qstr = "SELECT time, pos, diff from blocks where id=?"
        else:
            qstr = "SELECT time, "+type+" from stats where last_block=?"
        global database
        cursor = database.conn.cursor()
        query = cursor.execute(qstr,(id,));    
        stats = cursor.fetchone();
        if stats is None:
            print "stats "+str(id)+" not found"
            return "stats not found"
        stats = self.rowtodict(stats)
        return stats
    def get_block(self,block_id,tojson=True):
        try:
            id = int(block_id)
        except ValueError:
            return "block id must be a number"
        global database
        cursor = database.conn.cursor()
        query = cursor.execute(self.block_query, (id,))
        block = cursor.fetchone()
        if block is None:
            return "block not found"
        block = self.rowtodict(block)
        if tojson:
            return json.dumps(self.block_to_json(block))
        return self.block_to_json(block)
            
    def get_block_count(self):
        global database
        cursor = database.conn.cursor()
        query = cursor.execute(self.last_query)
        row = cursor.fetchone()
        if row is None:
            return "failed to fetch last block count"
        value = row[0]
        return value



class Blocks(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, id=None):
        if id == None:
            cherrypy.response.status = 500
            return "Add a block number or the keyword last to the url: blocks/86754"
        try:
            id = int(id)
        except ValueError:
            cherrypy.response.status = 500
            return "block id must be a number"
        if id < 10000000:
            return self.blockchain.get_block(id)
        cherrypy.response.status = 500
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
            cherrypy.response.status = 500
            return "count must be a number"
        if count > 10:
            cherrypy.response.status = 500
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
            cherrypy.response.status = 500
            return "block height must be a number"
        if id < 10000000:
            return json.dumps(self.blockchain.get_stats(id))
        cherrypy.response.status = 500
        return "block height too large"

class CompareLastStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, delta):
        try:
            delta = int(delta)
        except ValueError:
            cherrypy.response.status = 500
            return "delta must be a number"
        last = self.blockchain.get_block_count() - 1
        if delta > last:
            cherrypy.response.status = 500
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
            cherrypy.response.status = 500
            return "block id and delta must be numbers"
        if delta > first:
            cherrypy.response.status = 500
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
            cherrypy.response.status = 500
            return "first and second block ids must be numbers"
        if second > first:
            cherrypy.response.status = 500
            return "first id must be greater then second id"
        first_stats = self.blockchain.get_stats(first,False)
        second_stats = self.blockchain.get_stats(second,False)
        return blockchain.compare_stats(first_stats,second_stats)
        

class DataSeries(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, type, start):
        if type != 'diff' and type != 'inflation_rate' and type != 'money_supply':
            cherrypy.response.status = 500
            return "type must be diff or inflation_rate"
        try:
            start = int(start)
        except ValueError:
            cherrypy.response.status = 500
            return "start must be a number"
        block_count = self.blockchain.get_block_count()
        if(start > block_count):
            # avoid caching a bad response
            cherrypy.response.status = 500
            return "start must be less then block count"
        current_block = start;
        resolution = 144;
        limit = 0; # how many blocks before start to stop at
        results = list()
        calc_inflation = 0
        if(type == 'inflation_rate'):
            type = 'money_supply'
            calc_inflation = 1
            limit = 2016
        while current_block - limit > 0:
            #print "processing "+str(current_block)
            curr = self.blockchain.get_series_stats(type,current_block)
            if(not isinstance(curr,dict)):
                return curr
            if type == 'diff':
                while curr['POS'] == "true":
                    print "decrementing to find POS: "+str(current_block)
                    current_block = current_block - 1;
                    curr = self.blockchain.get_series_stats(type,current_block)
                    if(not isinstance(curr,dict)):
                        return curr
            time = curr['time']
            #print time
            if(calc_inflation):
                prev = self.blockchain.get_series_stats(type,current_block-2016)
                dur = curr['time'] - prev['time']
                inf_rate = (curr["money_supply"] - prev["money_supply"]) / 1e6
                total_seconds = dur / 1e3
                times_in_year = 31536000 / float(total_seconds)
                inf_rate = 100*inf_rate * times_in_year / (curr['money_supply']/1e6)
                templist = [time, inf_rate]
            else:
                if(type == 'money_supply'):
                    templist = [time, curr[type]/1e6]
                else:    
                    templist = [time, curr[type]]
            results.insert(0,templist)
            current_block = current_block - resolution;
        #print results
        return json.dumps(results)

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
            cherrypy.response.status = 500
            return "count must be a number"
        if count > 10:
            cherrypy.response.status = 500
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
        cherrypy.response.status = 404
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

api.series = DataSeries(blockchain)

config = {'/':
    {
        'request.dispatch' : cherrypy.dispatch.MethodDispatcher()
    }
}
application = cherrypy.tree.mount(api,"/api",config)
cherrypy.config.update({'error_page.404': error_404, 
                        #'environment':'production',
                        'log.error_file': '/app/logs/api_server.error.log',
                        'log.access_file': '/app/logs/api_server.access.log'})

if __name__ == '__main__':
    #cherrypy.quickstart(application)
    cherrypy.server.unsubscribe()
    server = cherrypy._cpserver.Server()
    server.socket_host = "127.0.0.1"
    server.socket_port = 8081
    server.thread_pool = 30
    server.subscribe()
    cherrypy.engine.subscribe('start_thread', connect)
    cherrypy.engine.start() 
    cherrypy.engine.block()

