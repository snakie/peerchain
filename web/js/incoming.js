var last_block = 0;
var blocks = new Array();
var txns = new Array();
var loader;

function block_to_row(block) {
       var cells = [];
       cells.push("<tr>");
       cells.push("<td><a href=\"/api/blocks/"+block.id+"\">"+block.id+"</td>");
       cells.push("<td><abbr class=\"timeago\" title=\""+block.time+"\">"+block.time+"</abbr></td>");
       cells.push("<td>"+(block.pos == "true" ? "POS" : "POW")+"</td>");
       cells.push("<td>"+(block.pos == "true" ? parseFloat(block.difficulty).toFixed(2) : (parseFloat(block.difficulty) / 1e6).toFixed(2) + 'M')+"</td>");
       cells.push("<td>"+parseFloat(block.reward).toFixed(2)+"</td>");
       cells.push("<td>"+block.txcount+"</td>");
       cells.push("<td>"+parseFloat(block.received).toFixed(2)+"</td>");
       cells.push("<td>"+parseFloat(block.destroyed).toFixed(2)+"</td>");
       cells.push("<td>"+(block.pos == "true" ? parseFloat(block.staked).toFixed(2) : '-')+"</td>");
       cells.push("<td>"+(block.pos == "true" ? parseFloat(block.stakeage).toFixed(2) : '-')+"</td>");
       cells.push("</tr>");
       return cells;
}
function stats_to_row(stats) {
       var cells = [];
       cells.push("<tr>");
       cells.push("<td><a href=\"/api/network/"+stats.last_block+"\">"+stats.last_block+"</td>");
       cells.push("<td><abbr class=\"timeago\" title=\""+stats.time+"\">"+stats.time+"</abbr></td>");
       cells.push("<td>"+stats.pow_blocks+"</td>");
       cells.push("<td>"+parseFloat(stats.pow_difficulty / 1e6).toFixed(2)+"M</td>");
       cells.push("<td>"+stats.pos_blocks+"</td>");
       cells.push("<td>"+parseFloat(stats.pos_difficulty).toFixed(2)+"</td>");
       cells.push("<td>"+parseFloat(stats.mined_coins).toFixed(2)+"</td>");
       cells.push("<td>"+parseFloat(stats.minted_coins).toFixed(2)+"</td>");
       cells.push("<td>"+parseFloat(stats.destroyed_fees).toFixed(2)+"</td>");
       cells.push("<td>"+parseFloat(stats.money_supply).toFixed(2)+"</td>");
       cells.push("<td>"+stats.transactions+"</td>");
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
function compare_to_row(compare) {
    var cells = []
    cells.push("<tr>");
    cells.push("<td><a href=\"/api/compare/delta/"+compare.last_block+"/"+network_review+"\">"+compare.last_block+"</td>");
    cells.push("<td><a href=\"/api/network/"+compare.last_block+"\">"+parseFloat(compare.money_supply_end).toFixed(2)+"</td>");
    cells.push("<td>"+parseFloat(100*compare.pos_blocks_delta/(compare.pos_blocks_delta+compare.pow_blocks_delta)).toFixed(2)+"%</td>");
    cells.push("<td>"+(parseFloat(compare.pos_difficulty_delta) > 0 ? "+" : "")+parseFloat(compare.pos_difficulty_delta).toFixed(2)+"</td>");
    cells.push("<td>"+(parseFloat(compare.pow_difficulty_delta) > 0 ? "+" : "")+parseFloat(compare.pow_difficulty_delta / 1e6).toFixed(2)+"M</td>");
    cells.push("<td>"+(parseFloat(compare.pow_block_reward_delta) > 0 ? "+" : "")+parseFloat(compare.pow_block_reward_delta).toFixed(2)+"</td>");
    cells.push("<td><a href=\"charts.html\">"+(parseFloat(compare.inflation_rate) > 0 ? "+" : "")+compare.inflation_rate+"%</a></td>");
    cells.push("<td>+"+parseFloat(compare.mined_coins_delta).toFixed(2)+"</td>");
    cells.push("<td>+"+parseFloat(compare.minted_coins_delta).toFixed(2)+"</td>");
    cells.push("<td>-"+parseFloat(compare.destroyed_fees_delta).toFixed(2)+"</td>");
    cells.push("<td>"+compare.duration+"</td>");
    cells.push("</tr>");
    return cells;
}
function insert_index(header,id) {
    var l = $("#"+header+" tr").size();
    var j = 0;
    for(i=1;i<l;i++) {
        var height = parseInt($("#"+header+" tr:eq("+i+") td:first a").html());
        //console.log("checking id:"+height);
        if(id == height)
            return -1;
        if (id+1 == height)
            j = i;
    }
    return j;
}
function add_block(block) {
    block.time = block.time.replace(' UTC','+0000')
    var cells = block_to_row(block);
    var index = insert_index('blocks',block.id);
    if(index < 0) {
        console.log("already existing block "+block.id)
        return;
    }
    $("#blocks tr:eq("+index+")").after(cells.join(""));
    console.log("adding block "+block.id);
    if($("#blocks tr").size() > block_count+1) {
        $("#blocks tr:last").remove();
    }
    $("abbr.timeago").timeago();
} 
function add_comparison(stats) {
    var cells = compare_to_row(stats);
    console.log("adding comparison "+stats.last_block);
    $("#review tr:eq(1)").after(cells.join(""));
    $("#review tr:last").remove();

}
function add_tx(tx) {
    var cells = txn_to_row(tx)
    $("#txn_header").after(cells.join(""));
    console.log("adding tx: "+tx.hash);
    if($("#txns tr").size() > tx_count+1) {
        $("#txns tr:last").remove();
    }
    $("abbr.timeago").timeago();

}
function add_stats(stats) {
    stats.time = stats.time.replace(' UTC','+0000')
    var cells = stats_to_row(stats);
    var index = insert_index('stats',stats.last_block);
    if(index < 0) {
        console.log("already existing stats "+stats.last_block)
        return;
    }
    $("#stats tr:eq("+index+")").after(cells.join(""));
    console.log("adding stats "+stats.last_block);
    if($("#stats tr").size() > network_count+1) {
        $("#stats tr:last").remove();
    }
    $("abbr.timeago").timeago();
}
var pushstream;
function message_received(text, id, channel) {
    console.log('web socket message on channel: "'+channel+'" id: "'+id+'"')
    //console.log(text);
    if (channel == 'blocks') {
        add_block(text);
    } else if(channel == 'tx') {
        add_tx(text);
        if($("#text-loader").size() == 0) {
            clearInterval(loader);
        }
    } else if(channel == 'delta') {
        add_comparison($.parseJSON(text));
    } else if(channel == 'network') {
        add_stats(text);
    } else if(channel == 'disconnect') {
        console.log('received disconnect')
        pushstream.connect();
    }
}
function ajax_blockfetch() {
    $.ajax({ url: "/api/blocks/last/"+block_count, dataType: "json", success: function(json) {
    var blocks = json.blocks;
    $.each( blocks, function( index, block ) {
       add_block(block)
       $("abbr.timeago").timeago()
    });
   }
});
}
function ajax_networkfetch() {
    $.ajax({ url: "/api/network/last/"+network_count, dataType: "json", success: function(json) {
    var stats = json.data;
    $.each( stats, function( index, stat ) {
       add_stats(stat)
       $("abbr.timeago").timeago()
    });
   }
});
}
function ajax_comparefetch() {
    $.ajax({ url: "/api/compare/last/"+network_review, dataType: "json", success: function(json) {
        add_comparison(json);
   }
});
}
function get_stream(published_after) {
    var temp = new PushStream({
        host: window.location.hostname,
        port: window.location.port,
        modes: "websocket",
        messagesPublishedAfter: published_after,
        messagesControlByArgument: true
    });
    return temp;

}
function get_stats(id) {
    var stats;
    $.ajax({ url: "/api/network/"+id, dataType: "json",
        async: false, success: function( index, nstats) {
            stats = nstats;
        } });
    return stats;
}
function load_network_review() {
    //looking for an ajax call /compare/last/2016
}
jQuery(document).ready(function() {
    pushstream = get_stream(7200);
    pushstream.onmessage = message_received;
    for(i=0;i<channels.length;i++) {
        pushstream.addChannel(channels[i])
    }
    if(typeof block_count === 'number')
        ajax_blockfetch();
    if(typeof network_count === 'number')
        ajax_networkfetch();
    if($("#text-loader").size() > 0) {
        loader = setInterval(function () {
            //console.log("adding loading ellipses");
            var span = $("#text-loader span:eq(0)");
            var ellipsis = span.html();
            ellipsis = ellipsis + ".";
            if (ellipsis.length > 5) {
                ellipsis = ".";
            }
            span.html(ellipsis);
        }, 1000);
     }
     if(typeof network_review === 'number') {
        ajax_comparefetch();
     }
     pushstream.connect();
 });

