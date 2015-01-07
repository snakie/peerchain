#!/app/virt/bin/python

import sys
sys.stdout = sys.stderr

import atexit
import re
import bitcoinrpc
import threading
import cherrypy, json
import datetime
import sqlite3
sys.path.append("/app/lib/bitcointools")
from deserialize import *
from BCDataStream import *


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
        #block["difficulty"] = format(block["difficulty"],'.8f')
        block["reward"] = format(block["reward"] / 1e6,'.6f')
        block["sent"] = format(block["sent"] / 1e6,'.6f')
        block["pos"] = block["pos"].lower()
        block["received"] = format(block["received"] / 1e6,'.6f')
        block["destroyed"] = format(block["destroyed"] / 1e6,'.6f')
        block["stakeage"] = format(block["stakeage"],'.2f')
        block["time"] = datetime.datetime.utcfromtimestamp(block["time"] / 1e3).strftime("%Y-%m-%d %H:%M:%S+0000")
        #print block["hashPrevBlock"]
        return block
    def stats_to_json(self,stats):
        stats["mined_coins"] = format(stats["mined_coins"] / 1e6,'.6f')
        stats["minted_coins"] = format(stats["minted_coins"] / 1e6,'.6f')
        stats["money_supply"] = format(stats["money_supply"] / 1e6,'.6f')
        stats["destroyed_fees"] = format(stats["destroyed_fees"] / 1e6,'.6f')
        stats["pow_block_reward"] = format(stats["pow_block_reward"] / 1e6,'.6f')
        #stats["pow_difficulty"] = format(stats["pow_difficulty"],'.2f')
        stats["pos_difficulty"] = format(stats["pos_difficulty"],'.8f')
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
        ret['pos_blocks_delta'] = first['pos_blocks'] - second['pos_blocks']
        ret['pos_difficulty_delta'] = format(first['pos_difficulty'] - second['pos_difficulty'],'.8f')
        ret['pow_blocks_delta'] = first['pow_blocks'] - second['pow_blocks']
        ret['pow_difficulty_delta'] = format(first['pow_difficulty'] - second['pow_difficulty'],'.8f')
        ret['pow_block_reward_delta'] = format((first['pow_block_reward'] - second['pow_block_reward']) / 1e6,'.6f')
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
        ret["mined_coins_delta"] = format((first["mined_coins"]-second["mined_coins"]) / 1e6,'.6f')
        ret["minted_coins_delta"] = format((first["minted_coins"]-second["minted_coins"]) / 1e6,'.6f')
        ret["destroyed_fees_delta"] = format((first["destroyed_fees"]-second["destroyed_fees"]) / 1e6,'.6f')
        #print first
        return ret
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
    def get_block(self,block_id,tojson=False):
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
        cherrypy.response.headers['Content-Type'] = "text/plain"
        if id == None:
            cherrypy.response.status = 500
            return "Add a block number or the keyword last to the url: blocks/86754"
        try:
            id = int(id)
        except ValueError:
            cherrypy.response.status = 500
            return "block id must be a number"
        if id < 10000000:
            return json.dumps(self.blockchain.get_block(id),indent=4,sort_keys=True)
        cherrypy.response.status = 500
        return "block id too large"

class LastBlock(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, count=None):
        cherrypy.response.headers['Content-Type'] = "text/plain"
        if count == None:
            count = 1
            last_id = self.blockchain.get_block_count()
            return json.dumps(self.blockchain.get_block(last_id),indent=4,sort_keys=True)
        try:
            count = int(count)
        except ValueError:
            cherrypy.response.status = 500
            return "count must be a number"
        if count > 10:
            cherrypy.response.status = 500
            return "count cannot be greater then 10"
        last_id = self.blockchain.get_block_count()
        data = { 'last' : last_id }
        blocks = []
        for c in range(count):
            curr = last_id-c
            blocks.append(self.blockchain.get_block(curr,False))
        data['blocks'] = blocks;
        cherrypy.response.headers['Content-Type'] = "text/plain"
        return json.dumps(data,indent=4,sort_keys=True)

class Stats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, id=None):
        cherrypy.response.headers['Content-Type'] = "text/plain"
        if id == None:
            return "Add a block number to the url: network/86754"
        try:
            id = int(id)
        except ValueError:
            cherrypy.response.status = 500
            return "block height must be a number"
        if id < 10000000:
            return json.dumps(self.blockchain.get_stats(id),indent=4,sort_keys=True)
        cherrypy.response.status = 500
        return "block height too large"

class CompareLastStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, delta):
        cherrypy.response.headers['Content-Type'] = "text/plain"
        try:
            delta = int(delta)
        except ValueError:
            cherrypy.response.status = 500
            return "delta must be a number"
        last = self.blockchain.get_block_count()
        if delta > last:
            cherrypy.response.status = 500
            return "delta must be less then total block height"
        first_stats = self.blockchain.get_stats(last,False)
        second_stats = self.blockchain.get_stats(last-delta,False)
        return json.dumps(blockchain.compare_stats(first_stats,second_stats),indent=4,sort_keys=True)

class CompareDeltaStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, first, delta):
        cherrypy.response.headers['Content-Type'] = "text/plain"
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
        return json.dumps(blockchain.compare_stats(first_stats,second_stats),indent=4,sort_keys=True)

class CompareStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, first, second):
        cherrypy.response.headers['Content-Type'] = "text/plain"
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
        return json.dumps(blockchain.compare_stats(first_stats,second_stats),indent=4,sort_keys=True)
        

class DataSeries(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, type, start):
        cherrypy.response.headers['Content-Type'] = "text/plain"
        allowed_types = ['destroyed_fees',
                         'inflation_rate',
                         'mined_coins',
                         'minted_coins',
                         'money_supply',
                         'pos_blocks',
                         'pos_difficulty',
                         'pow_block_reward',
                         'pow_blocks',
                         'pow_difficulty',
                         'transactions']
        formatting = ['destroyed_fees',
                      'mined_coins',
                      'minted_coins',
                      'money_supply',
                      'pow_block_reward']
        if not type in allowed_types:
            cherrypy.response.status = 500
            ret = "type must be one of the following:\n"
            for i in allowed_types:
                ret = ret + "    "+i+"\n"
            return ret
        format_value = False;
        if type in formatting:
            format_value = True;
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
                if(format_value):
                    templist = [time, curr[type]/1e6]
                else:    
                    templist = [time, curr[type]]
            results.insert(0,templist)
            current_block = current_block - resolution;
        #print results
        return json.dumps(results,indent=4,sort_keys=True)

class LastStats(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self, count=None):
        cherrypy.response.headers['Content-Type'] = "text/plain"
        if count == None:
            count = 1
            id = self.blockchain.get_block_count()
            return json.dumps(self.blockchain.get_stats(id),indent=4,sort_keys=True)
        try:
            count = int(count)
        except ValueError:
            cherrypy.response.status = 500
            return "count must be a number"
        if count > 10:
            cherrypy.response.status = 500
            return "count cannot be greater then 10"
        last_id = self.blockchain.get_block_count()
        data = { 'last' : last_id }
        network = []
        for c in range(count):
            curr = last_id-c
            network.append(self.blockchain.get_stats(curr))
        data['data'] = network;
        return json.dumps(data,indent=4,sort_keys=True);

class BlockCount(object):
    exposed = True
    def __init__(self,blockchain):
        self.blockchain = blockchain
    def GET (self):
        return json.dumps(self.blockchain.get_block_count(),indent=4,sort_keys=True)

class Transaction(object):
    exposed = True
    def __init__(self,blockchain):
        self.daemon = daemon
    def GET (self,txhash,static=0):
        cherrypy.response.headers['Content-Type'] = "text/plain"
        return json.dumps(self.daemon.get_tx(txhash,static),indent=4,sort_keys=True)

class Peercoin(object):
    def __init__(self):
        self.creds = self.get_rpc_creds()
        self.connect_to_daemon()
    def get_rpc_creds(self): 
        conf = open('/app/conf/rpc_creds.conf','r')
        ex = re.compile("^rpc([a-z]+)=(.*)$");
        ret = {}
        for line in conf:
            res = ex.search(line)
            if res:
                type = res.group(1)
                val = res.group(2)
                ret[type] = val
        return ret
    def connect_to_daemon(self):
        self.conn = bitcoinrpc.connect_to_remote(
        self.creds['user'],self.creds['password'],host='127.0.0.1', port=9902);
    def get_tx(self,txhash,skip=0):
        # validation txhash here
        txhash = txhash.lower()
        if not re.match(r'^[a-f0-9]{64}$',txhash):
            return {"error" : "invalid transaction hash format"}
        try:
            print "trying ppcoind"
            tx = self.conn.gettransaction(txhash)
            confirmations = tx.confirmations;
            tx = tx.transaction[0]
            del tx['coindays']
            tx['confirmations'] = confirmations
            for out in tx["outpoints"]:
                out["value"] = format(int(out["value"]) / 1e6,'.6f')
            for inp in tx["inpoints"]:
                inp["value"] = format(int(inp["value"]) / 1e6,'.6f')
            tx['time'] = datetime.datetime.utcfromtimestamp(tx["time"]).strftime("%Y-%m-%d %H:%M:%S+0000")
            return tx
        except bitcoinrpc.exceptions.InvalidAddressOrKey:
            print "checking elsewhere";
        template = self.conn.proxy.getblocktemplate()
        txns = template["transactions"];
        txdata = None
        for tx in txns:
            if tx["hash"] == txhash:
                txdata = tx["data"]
                break
        if txdata:
            raw = BCDataStream()
            raw.write(txdata.decode('hex_codec'))
            tx = parse_Transaction(raw)
            dtx = deserialize_Transaction_json(tx)
            dtx["confirmations"] = 0
            dtx["txid"] = txhash;
            dtx['time'] = datetime.datetime.utcfromtimestamp(tx["time"]).strftime("%Y-%m-%d %H:%M:%S+0000")
            #print dtx
            for inp in dtx["inpoints"]:
                old_tx = self.get_tx(inp["previoustx"])
                #print old_tx
                inp['value'] = old_tx['outpoints'][inp["previoustxindex"]]['value']
                inp['scriptpubkey'] = old_tx['outpoints'][inp["previoustxindex"]]['scriptpubkey']
                inp['peercoinaddress'] = old_tx['outpoints'][inp["previoustxindex"]]['peercoinaddress']
            return dtx;
        cherrypy.response.status = 500
        return {'error' : 'tx not found'}



class Index(object):
    exposed = True
    def GET(self):
        usage = """
  peercoin blockchain json api
    by snakie (snakie at yahoo.com)
    donations: PGiNfS4KTmb7W9GDxrA54tYTRhmSK36Pyj
        
  supported methods:

    blocks/count - fetch total block count
    blocks/<id> - fetch block meta data
    blocks/last - fetch last block
    blocks/last/<n> - fetch last n blocks

    tx/<hash> - fetch dump of transaction

    network/<id>  - fetch network statistics at a block number
    network/last - fetch last block
    network/last/<n> - fetch last n network statistics

    compare/<first_id>/<second_id> - compare network stats for two block heights
    compare/delta/<id>/<delta> - compare network stats for a block 'id' and block 'id-delta'
    compare/last/<delta> - compare last block and 'last block - delta' network stats

  Please find examples below at block height 152408:
 
    Block Count: 
      http://peerchain.net/api/blocks/count 

      152408

    Block Info: 
      http://peerchain.net/api/blocks/last
      http://peerchain.net/api/blocks/152408

    {
    "bits": "1c0e0f2c", 
    "chain": 0, 
    "destroyed": "0.000000", 
    "difficulty": 18.208355220000001, 
    "hash": "93e353975d62518bc218136f249e990d32d01f0c7ea6fd8708ce5b70a11c154b", 
    "hashMerkleRoot": "eec6bb63cfd7e22d677c4848944c5082bcc997d60598f28915f9529a69d08d1a", 
    "hashPrevBlock": "dd475bb728a2dcec663acab9c4d69e7535e982504bda06daf00ef999fad76d1c", 
    "id": 152408, 
    "nonce": 0, 
    "pos": "true", 
    "received": "0.000000", 
    "reward": "0.570000", 
    "sent": "0.000000", 
    "stakeage": "222.83", 
    "staked": "94.930000", 
    "time": "2015-01-07 03:13:46+0000", 
    "txcount": 0
    }  

    Similar to above but with more blocks:
      http://peerchain.net/api/blocks/last/2

    {
    "blocks": [
        {
            ..snip..
            "id": 152408, 
            ..snip..
        }, 
        {
            ..snip..
            "id": 152407, 
            ..snip..
        }
    ], 
    "last": 152408
    }

    Transaction Info:
      http://peerchain.net/api/tx/9faa5fadfd9b84448c3ee7fb381f69469587bac57a0432edd71e894ceb302517

    {
    "confirmations": 0, 
    "inpoints": [
        {
            "peercoinaddress": "PVcfdVWNEaUjr8mcaExyBnmpubAL2S3rSE", 
            "previoustx": "b856bc29f2602a57608c7413beb877b3d8c8e4099ea4856bf25013e183ad1d89", 
            "previoustxindex": 0, 
            "scriptpubkey": "OP_DUP OP_HASH160 e6a2d3a34cbabc8816eb79dda74c6589aa9c8e52 OP_EQUALVERIFY OP_CHECKSIG", 
            "scriptsig": "30440220122ef4ee39eaa1e0320dd5fb48f4271d07d9637cc82c30b7c35fb17ae7a4256d02203964d54365f708d6ad8817149952906428551b35994e2556705d57fa8c464e9d0121039e543378a861023ae05dd2ceacd0325c89d88b6f73e9923edb6fb32791a6a46a", 
            "value": "1.774058"
        }
    ], 
    "outpoints": [
        {
            "peercoinaddress": "PBU3M1TmSBJB9FufYpzaDLddxSkmsYufhd", 
            "scriptpubkey": "DUP HASH160 1f8ef2463e7d4cd587ff9009a0570f7f6ea7c6c5 EQUALVERIFY CHECKSIG", 
            "value": 0.104143
        }, 
        {
            "peercoinaddress": "PWTyLxNYwgEkCtEvan8SrfMn4ZPoHgtnZb", 
            "scriptpubkey": "DUP HASH160 eff5ff192699fa019e81449ab243863cfc6f9fa5 EQUALVERIFY CHECKSIG", 
            "value": 1.659915
        }
    ], 
    "time": "2015-01-07 04:24:16+0000", 
    "txid": "9faa5fadfd9b84448c3ee7fb381f69469587bac57a0432edd71e894ceb302517"
    }

    Network Statistics:
      http://peerchain.net/api/network/152408
      http://peerchain.net/api/network/last

    {
    "destroyed_fees": "5061.350508", 
    "last_block": 152408, 
    "mined_coins": "21777389.320000", 
    "minted_coins": "219929.820000", 
    "money_supply": "21992257.789492", 
    "pos_blocks": 116244, 
    "pos_difficulty": "18.20835522", 
    "pow_block_reward": "79.610000", 
    "pow_blocks": 36165, 
    "pow_difficulty": 248904953.27599999, 
    "time": "2015-01-07 03:13:46+0000", 
    "transactions": 408018
    } 

    Similar to above but with more data:
      http://peerchain.net/api/network/last/2

    {
    "data": [
        {
            ..snip..
            "last_block": 152408, 
            ..snip..
        }, 
        {
            ..snip..
            "last_block": 152407, 
            ..snip..
        }
    ], 
    "last": 152408
    }

    Compare the  last 8 blocks:
      http://peerchain.net/api/compare/152408/152400
      http://peerchain.net/api/compare/last/8
      http://peerchain.net/api/compare/delta/152408/8

    {
    "block_delta": 2016, 
    "destroyed_fees_delta": "50.461375", 
    "duration": "12 days, 0:20:42", 
    "first_block": 150392, 
    "inflation_rate": "3.75", 
    "last_block": 152408, 
    "mined_coins_delta": "22741.460000", 
    "minted_coins_delta": "4430.130000", 
    "money_supply_delta": "27121.128625", 
    "money_supply_end": "21992257.789492", 
    "pos_blocks_delta": 1732, 
    "pos_difficulty_delta": "0.16475234", 
    "pow_block_reward_delta": "-0.690000", 
    "pow_blocks_delta": 284, 
    "pow_difficulty_delta": "8488094.71700001", 
    "transactions": 4460
    }
       """;
        cherrypy.response.headers['Content-Type'] = "text/plain"
        return usage
    def default(self):
        cherrypy.response.status = 404
        return "method not implemented"

def error_404(status,message,traceback,version):
    return "method not implemented"

api = Index()
blockchain = Blockchain()
daemon = Peercoin()

api.blocks = Blocks(blockchain)
api.blocks.last = LastBlock(blockchain)
api.blocks.count = BlockCount(blockchain)

api.network = Stats(blockchain)
api.network.last = LastStats(blockchain)

api.compare = CompareStats(blockchain)
api.compare.delta = CompareDeltaStats(blockchain)
api.compare.last = CompareLastStats(blockchain)

api.tx = Transaction(daemon)

api.series = DataSeries(blockchain)

config = {'/':
    {
        'request.dispatch' : cherrypy.dispatch.MethodDispatcher()
    }
}
application = cherrypy.tree.mount(api,"/api",config)
cherrypy.config.update({'error_page.404': error_404, 
                        'environment':'production',
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

