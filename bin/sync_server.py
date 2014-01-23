#!/usr/local/bin/python

import bitcoinrpc, re, os, time, dateutil.parser, sys, datetime
from decimal import Decimal
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement

class Peercoin(object):
    def __init__(self):
        self.creds = self.get_rpc_creds()
        self.connect_to_daemon()
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
        if block["flags"] == "proof-of-stake":
            data["pos"] = True
        else: 
            data["pos"] = False
        data["hashprevblock"] = block["previousblockhash"]
        data["hashmerkleroot"] = block["merkleroot"]
        delta = dateutil.parser.parse(block["time"]).replace(tzinfo=None)-datetime.datetime(1970,1,1)
        data["time"] = (delta.days * 86400 + delta.seconds) * 1000
        #print data["time"]
        #sys.exit(1)
        data["bits"] = block["bits"]
        data["diff"] = block["difficulty"]
        data["nonce"] = block["nonce"]
        data["txcount"] = len(block["tx"])
        data["reward"] = int(block["mint"] * Decimal("1e6"))
        data["staked"] = 0
        data["sent"] = 0
        data["received"] = 0
        count = 0
        for tx in block["tx"]:
            txdata = self.conn.gettransaction(tx)
            for txn in txdata.transaction:
                for out in txn["outpoints"]:
                    data["received"] += int(out["value"])
                for inp in txn["inpoints"]:
                    data["sent"] += int(inp["value"])
            if data["pos"] and count < 2:
                data["staked"] += data["sent"]
            count += 1
            #print txdata
        if data["pos"]:
            data["sent"] = data["sent"] - data["staked"]
            data["received"] = data["received"] - data["staked"] - data["reward"]
        else:
            data["received"] = data["received"] - data["reward"]
        data["destroyed"] = data["sent"] - data["received"]
    
        return data    
        
class Database(object):
    def __init__(self,host="127.0.0.1",keyspace="peerchain"):
        self.cluster = Cluster([host])
        self.session = self.cluster.connect()
        self.session.set_keyspace(keyspace)
        self.last_query = SimpleStatement("SELECT value from counters where name='blocks'")
        self.blockhash_query = SimpleStatement("SELECT hash from blocks where id=%(id)s")
        self.increment_query = SimpleStatement("UPDATE counters SET value = value+1 where name = 'blocks'")
        self.decrement_query = SimpleStatement("UPDATE counters SET value = value-1 where name = 'blocks'")
        self.block_query = SimpleStatement("INSERT INTO blocks (id,chain,pos,hash,hashprevblock,hashmerkleroot,time,bits,diff,nonce,txcount,reward,staked,sent,received,destroyed) VALUES (%(id)s,%(chain)s,%(pos)s,%(hash)s,%(hashprevblock)s,%(hashmerkleroot)s,%(time)s,%(bits)s,%(diff)s,%(nonce)s,%(txcount)s,%(reward)s,%(staked)s,%(sent)s,%(received)s,%(destroyed)s)")
    def block_count(self):
          future = self.session.execute_async(self.last_query)
          try:
              rows = future.result()
          except Exception as e:
              return str(e)
          if len(rows) == 0:
              return "failed to fetch last block count"
          value = rows[0][0]
          return value
    def getblockhash(self,id):
          future = self.session.execute_async(self.blockhash_query, dict(id=id))
          rows = future.result()
          #print rows
          return rows[0][0]
    def decrement_counter(self):
          future = self.session.execute_async(self.decrement_query)
          rows = future.result()
    def increment_counter(self):
          future = self.session.execute_async(self.increment_query)
          #try:
          rows = future.result()
          #except Exception as e:
          #    return str(e)
    def insert_block(self,block):
        print block
        future = self.session.execute_async(self.block_query,block)
        #try:
        rows = future.result()
        #except Exception as e:
        #    return str(e)
        #print block
        self.increment_counter();



if __name__ == "__main__":
    daemon = Peercoin()
    db = Database()
    exit = 0
    v = False
    print "starting peercoin syncer.."
    while not exit:
        peercoin_height = daemon.block_count()
        db_height = db.block_count() - 1
        if v: print "ppcoind has "+str(peercoin_height)+" blocks"
        if v: print "database has "+str(db_height)+" blocks" 
        diff = peercoin_height - db_height;
        if v: print "syncing "+str(diff)+" blocks..."
        # check for re-org
        if diff == 0:
            if v: print "\nverifying chain"
            daemon_hash = daemon.conn.getblockhash(peercoin_height) 
            db_hash = db.getblockhash(peercoin_height)
            if v: print "daemon: "+daemon_hash
            if v: print "db    : "+db_hash
            if db_hash == "SEE NEXT BLOCK":
                print "warning database recently restored..waiting for new blocks.."
            else:
                if daemon_hash != db_hash:
                    print "warning ppc client and database lastest blocks differ!"
                else:
                    if v: print "ppc client and database newest chains in sync"
        # insert recently found blocks
        for i in reversed(range(diff)):
            id = peercoin_height - i;
            hash = daemon.conn.getblockhash(id)
            print "processing block: "+str(id)+" ("+hash+")"
            block = daemon.conn.getblock(hash)
            data = daemon.fill_in_data(hash,block)
            db.insert_block(data)
            print "entering sleep..",
            #sys.exit(1)
        print ".",
        sys.stdout.flush()
        time.sleep(30);

