var impactChart;

(function() {

var TEXT_ATTR = {"font": '9px "Arial"', stroke: "none", fill: "#fff"};
var DATE_ATTR = {"font": '9px "Arial"', stroke: "none", fill: "#000"};
var MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP",
              "OCT", "NOV", "DEC"];

function fillPeopleList($target_elem, people, colors, makeMouseOver) {
    $.each(people, function(i, person) {
        var $person_div = $('<div class="impact-person"/>');
        var $person_box = $('<div class="impact-person-box">&nbsp;</div>');
        var $person_name = $('<div class="impact-person-name"/>');
        $person_name.append(person.name);
        $person_box.css("backgroundColor", colors[person.author_id]);
        $person_div.append($person_box);
        $person_div.append($person_name);
        $target_elem.append($person_div);
        $person_div.addClass("impact-author-" + person.author_id);
        $person_div.mouseover(makeMouseOver(person.author_id));
    });
}

function selectPerson($base_elem, author_id) {
    $base_elem.find(".impact-person").removeClass("impact-selected");
    $base_elem.find(".impact-author-" + author_id)
            .addClass("impact-selected");
}

function calculateColors(people) {
    var colors = {};
    $.each(people, function(i, person) {
        colors[person.author_id] = Raphael.getColor();
    });
    return colors;
}

function scaleContributionSize(size, max_bucket_size) {
    return Math.max(
        Math.round(
            Math.log(size * (100000000 / max_bucket_size))) * 3,
        1)
}

function readableTimestamp(ts) {
    var date = new Date(ts * 1000);
    return date.getDate() + " " + MONTHS[date.getMonth()] + " " +
           date.getFullYear();
}

function drawImpact($chart_div, colors, buckets, paper, paths, labels,
                    makeMouseOver, max_bucket_size) {
    // You might not believe it, but this whole file is a rough port of the
    // *horrible* Raphael impact graph demo code. Whoever wrote that code
    // thought it was real cute to use one letter for variables all over.
    // I've tried my best to reintroduce sanity in this port, but this function
    // is where it breaks down and I run out of ideas for what the variables
    // stand for, so I just end up using the original variable names. Arrghh.
    // Blame/shoot http://raphaeljs.com/github/impact.html
    //
    // OH YEAH I almost forgot to complain about all the hardcoded numbers.
    // I'd take them out and make them tweakable constants, but I don't quite
    // understand all the different constants' interplay yet.

    // calculate paths and add bucket dates
    $.each(buckets, function(bucket_idx, bucket) {
        var height = 0;
        var x_coord = bucket_idx * 100;
        $.each(bucket.contributions, function(_, contribution) {
            var path = paths[contribution.author_id];
            if (!path) {
                path = paths[contribution.author_id] = {f: [], b: []}
            }
            path.f.push([x_coord, height, contribution.size]);
            height += scaleContributionSize(contribution.size,
                                            max_bucket_size);
            path.b.unshift([x_coord, height]);
            height += 2;
        });
        paper.text(x_coord + 25, height + 10, readableTimestamp(bucket.date))
                .attr(DATE_ATTR);
    });

    // actually draw the paths
    $.each(paths, function(author_id, path) {
        labels[author_id] = paper.set();
        path.p = paper.path().attr(
                {fill: colors[author_id], stroke: colors[author_id]})
        var path_str = "M".concat(
                path.f[0][0], ",", path.f[0][1], "L",
                path.f[0][0] + 50, ",", path.f[0][1]);
        var th = Math.round(
                path.f[0][1] + (
                        path.b[path.b.length - 1][1] - path.f[0][1])
                / 2 + 3);
        labels[author_id].push(
                paper.text(path.f[0][0] + 25, th,
                           path.f[0][2]).attr(TEXT_ATTR));
        var X = path.f[0][0] + 50;
        var Y = path.f[0][1];
        for (var j = 1; j < path.f.length; j++) {
            path_str = path_str.concat("C", X + 20, ",", Y, ",");
            X = path.f[j][0];
            Y = path.f[j][1];
            path_str = path_str.concat(X - 20, ",", Y, ",", X, ",", Y, "L",
                                       X += 50, ",", Y);
            th = Math.round(Y + (path.b[path.b.length - 1 - j][1] - Y) / 2 + 3)
            if (th - 9 > Y) {
                labels[author_id].push(
                        paper.text(X - 25, th, path.f[j][2]).attr(TEXT_ATTR));
            }
        }
        path_str = path_str.concat("L", path.b[0][0] + 50, ",", path.b[0][1],
                                   ",", path.b[0][0], ",", path.b[0][1]);
        for (var j = 1; j < path.b.length; j++) {
            path_str = path_str.concat(
                    "C", path.b[j][0] + 70, ",", path.b[j - 1][1], ",",
                    path.b[j][0] + 70, ",", path.b[j][1], ",",
                    path.b[j][0] + 50, ",", path.b[j][1], "L",
                    path.b[j][0], ",", path.b[j][1]);
        }
        path.p.attr({path: path_str + "z"});
        labels[author_id].hide();
        path.p.mouseover(makeMouseOver(author_id));
    });

    // resize the paper
    var max_x = 0;
    var max_y = 0;
    paper.forEach(function (el) {
        var bbox = el.getBBox();
        if (bbox.x2 > max_x) {
            max_x = bbox.x2;
        }
        if (bbox.y2 > max_y) {
            max_y = bbox.y2;
        }
    });
    paper.setSize(max_x, max_y);

    // scroll the chart to the far left if that makes sense to do.
    $chart_div.animate({scrollLeft: $chart_div.children("svg").width()}, 1);
}

impactChart = function(target_elem, data) {
    var $target_elem = $(target_elem);
    $target_elem.empty();
    $target_elem.addClass("impact-container");

    var $people_div = $('<div class="impact-people"/>');
    var colors = calculateColors(data.authors);

    var paths = {};
    var labels = {};
    var current_author_id = null;

    function makeMouseOver(author_id) {
        return (function() {
            if (current_author_id != null) {
                labels[current_author_id].hide();
            }
            current_author_id = author_id;
            labels[author_id].show();
            paths[author_id].p.toFront();
            labels[author_id].toFront();
            selectPerson($people_div, author_id);
        });
    }

    fillPeopleList($people_div, data.authors, colors, makeMouseOver);
    $target_elem.append($people_div);

    var $chart_div = $('<div class="impact-chart"/>');
    $target_elem.append($chart_div);

    var $end_div = $('<div class="impact-end"/>');
    $target_elem.append($end_div);

    var paper = Raphael($chart_div[0], 0, 0);

    drawImpact($chart_div, colors, data.buckets, paper, paths, labels,
               makeMouseOver, data.max_bucket_size);
}
})();
