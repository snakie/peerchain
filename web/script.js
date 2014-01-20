jQuery(document).ready(function() {
$.ajax({ url: "/api/blocks/last/10", dataType: "json", success: function(json) {
    var blocks = json.blocks;
    $.each( blocks, function( index, block ) {
       var cells = [];
       cells.push("<tr>");
       cells.push("<td>"+block.id+"</td>");
       cells.push("<td>"+(block.pos == true ? "POS" : "POW")+"</td>");
       cells.push("<td>"+jQuery.timeago(block.time)+"</td>");
       cells.push("<td>"+parseFloat(block.diff).toPrecision(10)+"</td>");
       cells.push("<td>"+block.reward+"</td>");
       cells.push("<td>"+block.txcount+"</td>");
       cells.push("<td>"+block.sent+"</td>");
       cells.push("<td>"+block.destroyed+"</td>");
       cells.push("</tr>");
       $("#blocks").append(cells.join(""));
    });
   }
});
});

