var last_block = 0;

function block_to_row(block) {
       var cells = [];
       cells.push("<tr>");
       cells.push("<td>"+block.id+"</td>");
       cells.push("<td><abbr class=\"timeago\" title=\""+block.time+"\">"+block.time+"</abbr></td>");
       cells.push("<td>"+(block.pos == true ? "POS" : "POW")+"</td>");
       cells.push("<td>"+(block.pos == true ? parseFloat(block.diff).toFixed(2) : (parseFloat(block.diff) / 1e6).toFixed(2) + 'M')+"</td>");
       cells.push("<td>"+parseFloat(block.reward).toFixed(2)+"</td>");
       cells.push("<td>"+block.txcount+"</td>");
       cells.push("<td>"+parseFloat(block.received).toFixed(2)+"</td>");
       cells.push("<td>"+parseFloat(block.destroyed).toFixed(2)+"</td>");
       cells.push("</tr>");
       return cells;
}
function add_block(block) {
    block.time = block.time.replace(' UTC','+0000')
    update_last_block(block);
    var cells = block_to_row(block);
    $("#table_header").after(cells.join(""));
    $("abbr.timeago").timeago()

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
    }
}
function update_last_block(block) {
    if (last_block < block.id) {
        last_block = block.id;
    }
}


jQuery(document).ready(function() {
$("abbr.timeago").timeago()
//var ws = new WebSocket("ws://"+window.location.host+"/ws/blocks.b5");
//$(ws).bind('message', function(e) { 
//            data = e.originalEvent.data;
//            console.log('web socket message:')
//            console.log(data);
//            var json = $.parseJSON(data);
//           json.time = json.time.replace(' UTC','+0000')
//            var cells = block_to_row(json);
//            $("#table_header").after(cells.join(""));
//            $("abbr.timeago").timeago()
//       }
//  );
//
var pushstream = new PushStream({
    host: window.location.hostname,
    port: window.location.port,
    modes: "websocket",
    messagesPublishedAfter: 600,
    messagesControlByArgument: true
});
pushstream.onmessage = message_received;
pushstream.addChannel('block');
pushstream.connect()
$.ajax({ url: "/api/blocks/last/10", dataType: "json", success: function(json) {
    var blocks = json.blocks;
    $.each( blocks, function( index, block ) {
       var cells = block_to_row(block)
       update_last_block(block);
       $("#blocks").append(cells.join(""));
       $("abbr.timeago").timeago()
    });
   }
});
});

