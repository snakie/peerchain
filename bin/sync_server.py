#!/usr/local/bin/python

import bitcoinrpc, re, os, time, dateutil.parser
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
    def fill_in_data(self,block):
        data = {}
        data["id"] = block["height"]
        if block["flags"] == "proof-of-stake":
            data["pos"] = "true"
        else: 
            data["pos"] = "false"
        data["hashprevblock"] = block["previousblockhash"]
        data["hashmerkleroot"] = block["merkleroot"]
        data["time"] = dateutil.parser.parse(block["time"]).strftime('%s')
        data["bits"] = block["bits"]
        data["diff"] = block["difficulty"]
        data["nonce"] = block["nonce"]
        data["txcount"] = len(block["tx"])
        data["reward"] = block["mint"]
        # still need staked, sent, received, destroyed
        for tx in block["tx"]:
            txdata = self.conn.gettransaction(tx)
            print txdata
            exit(1)
        return data    
        
class Database(object):
    def __init__(self,host="127.0.0.1",keyspace="peerchain"):
        self.cluster = Cluster([host])
        self.session = self.cluster.connect()
        self.session.set_keyspace(keyspace)
        self.last_query = SimpleStatement("SELECT value from counters where name='blocks'")
        self.counter_query = SimpleStatement("UPDATE counters SET value = value+1 where name = 'blocks'")
        self.block_query = SimpleStatement("INSERT INTO blocks (id,pos,hashprevblock,hashmerkleroot,time,bits,diff,nonce,txcount,reward,staked,sent,received,destroyed) VALUES (%(height)d,%(pos)s,'%(hashprevblock)s','%(hashmerkleroot)s',%(time)d,'%(bits)s',%(diff)f,%(nonce)u,%(txcount)d,%(staked)d,%(reward)d,%(sent)d,%(received)d,%(destroyed)d)")
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
    def increment_counter(self):
          future = self.session.execute_async(self.counter_query)
          try:
              rows = future.result()
          except Exception as e:
              return str(e)
    def insert_block(self,block):
        
        print block
        #self.increment_counter();



if __name__ == "__main__":
    daemon = Peercoin()
    db = Database()
    exit = 0;
    while not exit:
        peercoin_height = daemon.block_count()
        print "ppcoind has "+str(peercoin_height)+" blocks"
        db_height = db.block_count() - 1
        print "database has "+str(db_height)+" blocks" 
        diff = peercoin_height - db_height;
        print "syncing "+str(diff)+" blocks..."
        for i in range(diff):
            id = peercoin_height - i;
            hash = daemon.conn.getblockhash(id)
            print "processing block: "+str(id)+" ("+hash+")"
            block = daemon.conn.getblock(hash)
            data = daemon.fill_in_data(block)
            db.insert_block(data)

        time.sleep(30);

