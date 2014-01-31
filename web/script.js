var last_block = 0;

function block_to_row(block) {
       var cells = [];
       cells.push("<tr>");
       cells.push("<td><a href=\"/api/blocks/"+block.id+"\">"+block.id+"</td>");
       cells.push("<td><abbr class=\"timeago\" title=\""+block.time+"\">"+block.time+"</abbr></td>");
       cells.push("<td>"+(block.pos == true ? "POS" : "POW")+"</td>");
       cells.push("<td>"+(block.pos == true ? parseFloat(block.diff).toFixed(2) : (parseFloat(block.diff) / 1e6).toFixed(2) + 'M')+"</td>");
       cells.push("<td>"+parseFloat(block.reward).toFixed(2)+"</td>");
       cells.push("<td>"+block.txcount+"</td>");
       cells.push("<td>"+parseFloat(block.received).toFixed(2)+"</td>");
       cells.push("<td>"+parseFloat(block.destroyed).toFixed(2)+"</td>");
       cells.push("<td>"+(block.pos == true ? parseFloat(block.staked) : '-')+"</td>");
       cells.push("<td>"+(block.pos == true ? block.coindays : '-')+"</td>");
       cells.push("</tr>");
       return cells;
}
function txn_to_row(tx) {
    var cells = []
    cells.push("<tr>");
    cells.push("<td>"+tx.hash+"</td>");
    cells.push("<td><abbr class=\"timeago\" title=\""+tx.time+"\">"+tx.time+"</abbr></td>");
    cells.push("<td>"+parseFloat(tx.value).toFixed(2)+"</td>");
    cells.push("</tr>");
    return cells;
}
function add_block(block) {
    block.time = block.time.replace(' UTC','+0000')
    update_last_block(block);
    var cells = block_to_row(block);
    $("#table_header").after(cells.join(""));
    if($("#blocks tr td").length > 110) {
        console.log("block length: "+$("#blocks tr td").length);
        $("#blocks tr:last").remove();
    }
    $("abbr.timeago").timeago();
}
function add_tx(tx) {
    var cells = txn_to_row(tx)
    $("#txn_header").after(cells.join(""));
    if($("#txns tr td").length > 110) {
        console.log("txn length: "+$("#txns tr td").length);
        $("#txns tr:last").remove();
    }
    $("abbr.timeago").timeago();

}
function message_received(text, id, channel) {
    console.log('web socket message on channel: "'+channel+'" id: "'+id+'"')
    console.log(text);
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

