#!/usr/local/bin/python

import bitcoinrpc, re, os, time, dateutil.parser, sys, datetime, httplib, json, logging, pytz 
from dateutil.tz import tzlocal
from decimal import Decimal
from optparse import OptionParser
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
sys.path.append("/app/lib/bitcointools")
from deserialize import *
from BCDataStream import *


class Notify(object):
    def __init__(self,host,port,uri):
        self.host = host
        self.port = port
        self.uri = uri
    def stats_to_json(self,stats):
        stats["mined_coins"] = format(stats["mined_coins"] / 1e6,'.6f')
        stats["minted_coins"] = format(stats["minted_coins"] / 1e6,'.6f')
        stats["destroyed_fees"] = format(stats["destroyed_fees"] / 1e6,'.6f')
        stats["money_supply"] = format(stats["money_supply"] / 1e6,'.6f')
        return stats
    def block_to_json(self,block,time):
        block["staked"] = format(block["staked"] / 1e6,'.6f')
        block["diff"] = format(block["diff"],'.8f')
        block["reward"] = format(block["reward"] / 1e6,'.6f')
        block["sent"] = format(block["sent"] / 1e6,'.6f')
        block["received"] = format(block["received"] / 1e6,'.6f')
        block["destroyed"] = format(block["destroyed"] / 1e6,'.6f')
        block["time"] = time
        return block
    def post(self,data):
        conn = httplib.HTTPConnection(self.host,self.port)
        conn.request("POST", self.uri, json.dumps(data))
        res = conn.getresponse()
        try:
            rdata = json.loads(res.read())
            logging.info("notify: "+str(res.status)+' '+res.reason+' - '+rdata["subscribers"]+' subscriber(s)')
        except:
            logging.warning("notify: "+str(res.status)+' '+res.reason+' - failed to fetch subscribers')
        conn.close()
    def post_tx(self,data):
        data = data.transaction[0]
        self.post(data)
    def post_stats(self,data):
        jsondata = self.stats_to_json(data)
        self.post(jsondata)
    def post_block(self,data,time):
        jsondata = self.block_to_json(data,time)
        self.post(jsondata)
        #sys.exit(0);

class Peercoin(object):
    def __init__(self):
        self.creds = self.get_rpc_creds()
        self.connect_to_daemon()
        self.pos = re.compile("proof-of-stake")
    def get_rpc_creds(self): 
        home = os.getenv("HOME")
        conf = open(home+'/.ppcoin/ppcoin.conf','r')
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
    def block_count(self):
        return self.conn.getblockcount()
    def fill_in_data(self,hash,block):
        data = {}
        data["id"] = block["height"]
        data["hash"] = hash
        data["chain"] = 0
        data["txcount"] = len(block["tx"])
        if self.pos.match(block["flags"]):
            data["pos"] = True
            data["txcount"] = data["txcount"] - 2
        else: 
            data["pos"] = False
            data["stakeage"] = 0
            data["txcount"] = data["txcount"] - 1
        data["hashprevblock"] = block["previousblockhash"]
        data["hashmerkleroot"] = block["merkleroot"]
        delta = dateutil.parser.parse(block["time"]).replace(tzinfo=None)-datetime.datetime(1970,1,1)
        data["time"] = (delta.days * 86400 + delta.seconds) * 1000
        #print data["time"]
        #sys.exit(1)
        data["bits"] = block["bits"]
        data["diff"] = block["difficulty"]
        data["nonce"] = block["nonce"]
        data["reward"] = long(block["mint"] * Decimal("1e6"))
        data["staked"] = 0
        data["sent"] = 0
        data["received"] = 0
        count = 0
        for tx in block["tx"]:
            txdata = self.conn.gettransaction(tx)
            logging.debug(txdata)
            for txn in txdata.transaction:
                for out in txn["outpoints"]:
                    data["received"] += long(out["value"])
                for inp in txn["inpoints"]:
                    data["sent"] += long(inp["value"])
                if data["pos"] and count == 1:
                    data["stakeage"] = round(txn["coindays"] / (data["sent"]/1e6),2)
            if data["pos"] and count < 2:
                data["staked"] += data["sent"]
            count += 1
        if data["pos"]:
            data["sent"] = data["sent"] - data["staked"]
            data["received"] = data["received"] - data["staked"] - data["reward"]
        else:
            data["received"] = data["received"] - data["reward"]
        data["destroyed"] = data["sent"] - data["received"]
        #print data
    
        return data    
        
class Database(object):
    def __init__(self,host="127.0.0.1",keyspace="peerchain"):
        self.cluster = Cluster([host])
        self.session = self.cluster.connect()
        self.session.set_keyspace(keyspace)
        self.last_query = SimpleStatement("SELECT value from counters where name='blocks'")
        self.blockhash_query = SimpleStatement("SELECT hash from blocks where id=%(id)s")
        self.last_stats_query = SimpleStatement("SELECT * from stats where last_block=%(id)s")
        self.increment_query = SimpleStatement("UPDATE counters SET value = value+1 where name = 'blocks'")
        self.decrement_query = SimpleStatement("UPDATE counters SET value = value-1 where name = 'blocks'")
        self.delete_query = SimpleStatement("delete from blocks where id=%(id)s")
        self.delete_stats_query = SimpleStatement("delete from stats where last_block=%(id)s")
        self.stats_query = SimpleStatement("INSERT INTO stats (last_block,destroyed_fees,mined_coins,minted_coins,money_supply,pos_blocks,pow_blocks,time,transactions) VALUES (%(last_block)s,%(destroyed_fees)s,%(mined_coins)s,%(minted_coins)s,%(money_supply)s,%(pos_blocks)s,%(pow_blocks)s,%(time)s,%(transactions)s)")
        self.block_query = SimpleStatement("INSERT INTO blocks (id,chain,stakeage,pos,hash,hashprevblock,hashmerkleroot,time,bits,diff,nonce,txcount,reward,staked,sent,received,destroyed) VALUES (%(id)s,%(chain)s,%(stakeage)s,%(pos)s,%(hash)s,%(hashprevblock)s,%(hashmerkleroot)s,%(time)s,%(bits)s,%(diff)s,%(nonce)s,%(txcount)s,%(reward)s,%(staked)s,%(sent)s,%(received)s,%(destroyed)s)")
    def shutdown(self):
        self.cluster.shutdown()
    def block_count(self):
          future = self.session.execute_async(self.last_query)
          try:
              rows = future.result()
          except Exception as e:
              return str(e)
          if len(rows) == 0:
              return "failed to fetch last block count"
          value = rows[0][0]
          return int(value)
    def getblockhash(self,id):
          future = self.session.execute_async(self.blockhash_query, dict(id=id))
          rows = future.result()
          #print rows
          if len(rows) == 0:
            return None
          return rows[0][0]
    def get_stats(self,id):
          future = self.session.execute_async(self.last_stats_query,dict(id=id))
          rows = future.result()
          if rows:
            return rows[0]._asdict()
          return None
    def decrement_counter(self):
          future = self.session.execute_async(self.decrement_query)
          rows = future.result()
    def delete_block(self,id):
          future = self.session.execute_async(self.delete_query,dict(id=id))
          rows = future.result()
          future = self.session.execute_async(self.delete_stats_query,dict(id=id))
          rows = future.result()
          self.decrement_counter();
    def increment_counter(self):
          future = self.session.execute_async(self.increment_query)
          #try:
          rows = future.result()
          #except Exception as e:
          #    return str(e)
    def insert_block(self,block,stats):
        #print block
        future = self.session.execute_async(self.block_query,block)
        #try:
        rows = future.result()
        future = self.session.execute_async(self.stats_query,stats)
        rows = future.result()
        #except Exception as e:
        #    return str(e)
        #print block
        self.increment_counter();

class Syncer(object):
    def __init__(self):
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
        self.options = self.parse_args()
        self.block = None
        self.verify = None
        self.loop = None
        self.id = None
        self.tx = None
        self.update = None
        if self.options.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        if self.options.id:
            self.id = self.options.id
            logging.info("starting peercoin syncer for block height: "+str(self.id))
        elif self.options.update:
            self.update = self.options.update
            logging.info("starting peercoin syncer for block update: "+self.update)
        elif self.options.block:
            self.block = self.options.block
            logging.info("starting peercoin syncer for block: "+self.block)
        elif self.options.tx:
            self.tx = self.options.tx
            logging.info("starting peercoin syncer for tx: "+self.tx)
        elif self.options.loop:
            self.loop = self.options.loop
            logging.info("starting peercoin syncer in polling mode ("+self.loop+" s cycle)")
        elif self.options.verify:
            self.verify = True
            logging.info("verifying db and daemon hash consistency for lastest block in db")
        else:
            logging.info("starting peercoin syncing for one sync")  
        self.db = Database()
        self.dryrun = self.options.dryrun
        self.daemon = Peercoin()
        self.notify = Notify('127.0.0.1',80,'/broadcast/blocks')
        self.txnotify = Notify('127.0.0.1',80,'/broadcast/tx')
        self.networknotify = Notify('127.0.0.1',80,'/broadcast/network')
    def parse_args(self):
        version = '0.0.1'
        self.parser = OptionParser(usage="\nPeercoin Daemon Sync Utility "+version+"\nSync's the lastest blocks into the database by default\n$ %prog [options]", version="%prog "+version)
        self.parser.add_option("-d","--debug", action="store_true", dest="verbose", help="verbose debug output", default=False)
        self.parser.add_option("-v","--verify", action="store_true", dest="verify", help="check consistency for latest block between database and daemon", default=False)
        self.parser.add_option("-n","--dry-run", action="store_true", dest="dryrun", help="no database inserts", default=False)
        self.parser.add_option("-b","--block", dest="block", metavar='HASH', help="process only the block hash specified")
        self.parser.add_option("-t","--tx", dest="tx", metavar='TXHASH', help="send a transaction notify out")
        self.parser.add_option("-i","--height", dest="id", metavar='ID', help="process only the block id/height specified")
        self.parser.add_option("-u","--update", dest="update", metavar='ID', help="update block in db")
        self.parser.add_option("-l","--loop", dest="loop", metavar='CYCLE', help="polling mode with CYCLE seconds sleep")
        (options, args) = self.parser.parse_args()
        return options
    def get_heights(self):
        self.peercoin_height = self.daemon.block_count()
        self.db_height = self.db.block_count() - 1
        logging.debug("ppcoind has "+str(self.peercoin_height)+" blocks") 
        logging.debug("database has "+str(self.db_height)+" blocks")
        self.diff = self.peercoin_height - self.db_height;
    def check_chains(self):
        self.get_heights()
        logging.debug("verifying chain")
        daemon_hash = self.daemon.conn.getblockhash(self.peercoin_height) 
        db_hash = self.db.getblockhash(self.peercoin_height)
        if not db_hash:
            logging.info("lastest block not found in database, please sync first")
            logging.debug("daemon: "+daemon_hash)
            sys.exit(1)
        logging.debug("daemon: "+daemon_hash)
        logging.debug("db    : "+db_hash)
        if db_hash == "SEE NEXT BLOCK":
            logging.warning("database recently restored..waiting for new blocks..")
        else:
            if daemon_hash != db_hash:
                logging.warning("ppc client and database lastest blocks differ!")
                print >> sys.stderr, "warning ppc client and database lastest blocks differ!"
                logging.warning("daemon: "+daemon_hash)
                logging.warning("db    : "+db_hash)
            else:
                logging.info("ppc client and database newest chains in sync")
    def process_id(self):
        self.get_heights()
        hash = self.daemon.conn.getblockhash(int(self.id))
        self.insert_block(hash)
    def process_update(self):
        hash = self.daemon.conn.getblockhash(int(self.update))
        self.db.delete_block(int(self.update)) 
        self.insert_block(hash)
    def process_block(self):
        self.get_heights()
        self.insert_block(self.block)
    def process_tx(self):
        hash = self.tx
        tx_broadcast = dict(hash=hash, value=0);
        logging.info("processing tx hash: "+hash)
        template = self.daemon.conn.proxy.getblocktemplate()
        txns = template["transactions"];
        txdata = None
        for tx in txns:
            if tx["hash"] == hash:
                logging.info("tx found in mempool")
                txdata = tx["data"]
                break
        if txdata:
            raw = BCDataStream()
            raw.write(txdata.decode('hex_codec'))
            tx = parse_Transaction(raw)
            for out in tx["txOut"]:
                tx_broadcast["value"] += out["value"] 
        else:
            logging.info("unable to find tx in mempool")
            try:
                tx = self.daemon.conn.gettransaction(hash)
                tx = tx.transaction[0]
                logging.debug(tx)
                for out in tx["outpoints"]:
                    tx_broadcast["value"] += long(out["value"])
            except bitcoinrpc.exceptions.InvalidAddressOrKey:
                logging.info("tx not found in blockchain")
                sys.exit(1)
        date = datetime.datetime.fromtimestamp(tx["time"]).replace(tzinfo=tzlocal())
        tx_broadcast["time"] = date.strftime('%Y-%m-%d %H:%M:%S%z')
        tx_broadcast["value"] = format(tx_broadcast["value"] / 1e6,'.6f')
        self.txnotify.post(tx_broadcast)
    def update_stats(self,stats,time,data):
        if data["pos"]:
            stats["pos_blocks"] += 1
            stats["minted_coins"] += data["reward"]
        else:
            stats["pow_blocks"] += 1
            stats["mined_coins"] += data["reward"]
        stats["money_supply"] += data["reward"]
        stats["money_supply"] -= data["destroyed"]
        stats["destroyed_fees"] += data["destroyed"]
        stats["last_block"] += 1
        stats["transactions"] += data["txcount"]
        #delta = datetime.datetime.utcnow()-datetime.datetime(1970,1,1)
        #stats["time"] = (delta.days * 86400 + delta.seconds) * 1000
        stats["time"] = time

        return stats 
    def insert_block(self,hash):
        logging.info("processing block hash: "+hash)
        block = self.daemon.conn.getblock(hash)
        data = self.daemon.fill_in_data(hash,block)
        stats = self.db.get_stats(data["id"] - 1)
        #print data
        if stats:
            stats = self.update_stats(stats,block["time"],data)
            logging.debug(data)
            if self.dryrun:
                logging.info("not inserting block: dryrun enabled")
            else:
                logging.debug("inserting block: dryrun not enabled")
                self.db.insert_block(data,stats)
        else:
            logging.error("failed to find previous stats - unable to sync")
            # notifies on the websocket still go out
            self.notify.post_block(data,block["time"])
            sys.exit(1);
        #print stats
        # even though I may not have inserted the block
        self.notify.post_block(data,block["time"])
        self.networknotify.post_stats(stats)
        
    def insert_recent_blocks(self):
        for i in reversed(range(self.diff)):
            id = self.peercoin_height - i;
            hash = self.daemon.conn.getblockhash(id)
            logging.info("processing block: "+str(id))
            self.insert_block(hash)
            #print "entering sleep..",
            #sys.exit(1)
        #print ".",
    def process_diff(self):
        self.get_heights() 
        # check for re-org
        if self.diff == 0:
            logging.info('diff 0 - nothing to sync')
        else:            
            logging.debug("syncing "+str(self.diff)+" blocks...")
            self.insert_recent_blocks()
    def shutdown(self):
        self.db.shutdown()



if __name__ == "__main__":
    sync = Syncer()
    if sync.tx:
        sync.process_tx()
    elif sync.update:
        sync.process_update()
    elif sync.id:
        sync.process_id()
    elif sync.block:
        sync.process_block()
    elif sync.loop:
        while True:
            sync.process_diff()
            sys.stdout.flush()
            time.sleep(float(sync.loop));
    elif sync.verify:
        sync.check_chains()
    else:
        sync.process_diff()
        sync.check_chains()
    sync.shutdown()

