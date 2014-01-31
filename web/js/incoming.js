var last_block = 0;

function block_to_row(block) {
       var cells = [];
       cells.push("<div class=\"row\">");
       cells.push("<div class=\"col-md-1\"><a href=\"/api/blocks/"+block.id+"\">"+block.id+"</a></div>");
       cells.push("<div class=\"col-md-2\"><abbr class=\"timeago\" title=\""+block.time+"\">"+block.time+"</abbr></div>");
       cells.push("<div class=\"col-md-1\">"+(block.pos == true ? "POS" : "POW")+"</div>");
       cells.push("<div class=\"col-md-1\">"+(block.pos == true ? parseFloat(block.diff).toFixed(2) : (parseFloat(block.diff) / 1e6).toFixed(2) + 'M')+"</div>");
       cells.push("<div class=\"col-md-1\">"+parseFloat(block.reward).toFixed(2)+"</div>");
       cells.push("<div class=\"col-md-1\">"+block.txcount+"</div>");
       cells.push("<div class=\"col-md-1\">"+parseFloat(block.received).toFixed(2)+"</div>");
       cells.push("<div class=\"col-md-1\">"+parseFloat(block.destroyed).toFixed(2)+"</div>");
       cells.push("<div class=\"col-md-1\">"+(block.pos == true ? parseFloat(block.staked) : '-')+"</div>");
       cells.push("<div class=\"col-md-1\">"+(block.pos == true ? block.coindays : '-')+"</div>");
       cells.push("</div>");
       return cells;
}
function txn_to_row(tx) {
    var cells = []
    cells.push("<div class=\"row\">");
    cells.push("<div class=\"col-md-6\">"+tx.hash+"</div>");
    cells.push("<div class=\"col-md-2\"><abbr class=\"timeago\" title=\""+tx.time+"\">"+tx.time+"</abbr></div>");
    cells.push("<div class=\"col-md-1\">"+parseFloat(tx.value).toFixed(2)+"</div>");
    cells.push("</div>");
    return cells;
}
function add_block(block) {
    block.time = block.time.replace(' UTC','+0000')
    update_last_block(block);
    var cells = block_to_row(block);
    $("#table_header").after(cells.join(""));
    console.log("block length: "+$("#blocks div.row").size());
    if($("#blocks div.row").size() > 11) {
        $("#blocks div.row:last").remove();
    }
    $("abbr.timeago").timeago();
}
function add_tx(tx) {
    var cells = txn_to_row(tx)
    $("#txn_header").after(cells.join(""));
    console.log("txn length: "+$("#txns div.row").size());
    if($("#txns div.row").size() > 11) {
        $("#txns div.row:last").remove();
    }
    $("abbr.timeago").timeago();

}
function message_received(text, id, channel) {
    console.log('web socket message on channel: "'+channel+'" id: "'+id+'"')
    //console.log(text);
    if (channel == 'block') {
        if(text.id > last_block) {
            add_block(text);
        } else {
            console.log("block too old")
        }
    } else if(channel == 'tx') {
        add_tx(text);
    }
}
function update_last_block(block) {
    if (last_block < block.id) {
        last_block = block.id;
    }
}
function ajax_blockfetch() {
$.ajax({ url: "/api/blocks/last/10", dataType: "json", success: function(json) {
    var blocks = json.blocks;
    $.each( blocks, function( index, block ) {
       var cells = block_to_row(block)
       update_last_block(block);
       $("#blocks").append(cells.join(""));
       $("abbr.timeago").timeago()
       if(!connected) {
        connected = true;
        pushstream.connect();
       }
    });
   }
});

}

var connected = false;

jQuery(document).ready(function() {
var pushstream = new PushStream({
    host: window.location.hostname,
    port: window.location.port,
    modes: "websocket",
    messagesPublishedAfter: 7200,
    messagesControlByArgument: true
});
pushstream.onmessage = message_received;
pushstream.addChannel('block');
pushstream.addChannel('tx');
pushstream.connect();
});

