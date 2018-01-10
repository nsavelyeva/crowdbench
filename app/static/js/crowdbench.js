var graph_interval;

$(function() {

	$('onLoad', function() {

		if ($('#chartdiv').length) {

		    update_graph()
		    graph_interval = setInterval(function() {
		        update_graph()
		    }, 5000); //time in milliseconds;

		    $('input[name=y_axis]:radio').change(function () {
		        $('.amcharts-title tspan').html(this.title)
		        update_graph()
		    });

		    $('input[name^=Action]').change(function () {
		        update_graph()
		    });

		}

		return false;
	});  // onLoad function()

});  // function()


function draw_chart(data, fields) {
    colors = {"failed": "red", "passed": "green", "incomplete": "blue"}
    graphs = []
    for (i=0; i<fields.length; i++) {
        graphs[i] = {"title": fields[i],
		             "valueField": fields[i],
		             "type": "line",
		             "fillAlphas": 0,
		             "bullet": "round",
		             "lineColor": colors[fields[i]]
	    }
    }

	chart = AmCharts.makeChart("chartdiv", {
		"graphs": graphs,
		"type": "serial",
		"dataProvider": data,
		"categoryField": "timestamp",
		"titles": [{
            "text": document.querySelector('input[name=y_axis]:checked').title,
        }],
		"categoryAxis": {
			"gridCount": data.length,
			"autoGridCount": true,
			"labelRotation": 90,
			"title": "Timeline (seconds elapsed after test started) - Last hour activity",
		},
		"valueAxes": [{
		    "title": get_y_axis_title()
		}],
		"legend": {
			"useGraphSettings": true
		},
		"export": {
			"enabled": true,
			"position": "bottom-right"
		},
		"chartScrollbar": {
            "graph": "g1",
		    "autoGridCount": true,
            "scrollbarHeight": 40,
            "offset":5,
        },
        "chartCursor": {
           "limitToGraph":"g1"
        },
    }); // AmCharts.makeChart

    chart.addListener("rendered", zoomChart);
    zoomChart();
} // function draw_chart()


function zoomChart() {
    chart.zoomToIndexes(chart.dataProvider.length - 60, chart.dataProvider.length - 1);
}


function get_actions_string() {
    nodes = document.querySelectorAll('input[name^=Action]:checked')
    values = []
    for (i=0; i<nodes.length; i++) values[i] = nodes[i].value
    return values.join()
}


function get_y_axis_title() {
    value = document.querySelector('input[name=y_axis]:checked').value
    if (value == 'avgl' || value == 'avgd')
        return 'milliseconds'
    return 'op/sec'
}


function update_graph() {
    slave = document.getElementById('slave').value
	url = '/_get_chartdata'
	if (slave != 'total') {
	    url = 'http://' + slave + ':' + document.getElementById('web_port').value + url
	}
	url += '?test_run_id=' + document.getElementById('test_run_id').value
	url += '&y_axis=' + document.querySelector('input[name=y_axis]:checked').value
	url += '&actions=' + get_actions_string()
	url += '&slave=' + slave
	//alert(url)
	$.ajax({url: url,
	        type: "GET", dataType: 'JSONP', jsonpCallback: 'callback',
            headers: {"Access-Control-Allow-Origin": "*"},
    }).done(function (data) {
        console.log(data)
        draw_chart(data[slave], ["failed", "passed", "incomplete"])
        $('#status').html(data["status"])
        $('#started').html(human_time(data["started"]) + ' [timestamp: ' + data["started"] + ' ]')
		$('#finished').html(human_time(data["finished"]) + ' [timestamp: ' + data["finished"] + ' ]')
		$('#progress').html(data["progress"])
        update_summary()

        if (data["status"] != '' && data["status"] != 'IN PROGRESS') {
            clearInterval(graph_interval);
            states = {'FINISHED': 2, 'ABORTED': 3, 'CANCELLED': 3}
            $.getJSON("/_test_update",
                      {"test_run_title": document.getElementById('test_run_id').value,
                       "completed": data["finished"], "status": states[data["status"]]},
                      function(data) {
                          console.log('Updated local database ' + data)
	        });  // getJSON
		}

	});
}


function update_summary() {
    slave = document.getElementById('slave').value
	url = '/_get_summary'
	if (slave != 'total') {
	    url = 'http://' + slave + ':' + document.getElementById('web_port').value + url
	}
	url += '?test_run_id=' + document.getElementById('test_run_id').value
	url += '&slave=' + slave
	$.ajax({url: url,
	        type: "GET", dataType: 'JSONP', jsonpCallback: 'callback',
            headers: {"Access-Control-Allow-Origin": "*"},
    }).done(function (data) {
        console.log(data)
        content = '<h5>Summary of responses</h5>'
        content += '<table><tr><th>Count</th><th>Response Code</th><th>Response Reason</th></tr>'
        for (i=0; i<data.length; i++) {
            content += '<tr><td>' + data[i]['count'] + '</td>'
            content += '<td>' + data[i]['code'] + '</td><td>' + data[i]['reason'] + '</td></tr>'
        }
        content +=  '</table>'
        $('#summary').html(content)
        update_debug_info()
	});
}


function update_debug_info() {
    slave = document.getElementById('slave').value
	url = '/_get_logs'
	if (slave != 'total') {
	    url = 'http://' + slave + ':' + document.getElementById('web_port').value + url
	}
	url += '?test_run_id=' + document.getElementById('test_run_id').value
	url += '&slave=' + slave
	$.ajax({url: url,
	        type: "GET", dataType: 'JSONP', jsonpCallback: 'callback',
            headers: {"Access-Control-Allow-Origin": "*"},
    }).done(function (data) {
        console.log(data)
        content = '<h5>Debug information (limited to last 10 lines)</h5>'
        for (i=0; i<data.length; i++) {
            part = data[i].hasOwnProperty('host') ? ' ' + data[i]['host'].substring(0, data[i]['host'].indexOf(':')) : ''
            content += '<p><strong>Logs from Slave Host' + part + ':</strong></p>'
            content += '<p><i>Test run logs:</i><br>' + data[i]['logs']['testrun']
            content += '<p><i>Monitor agent logs:</i><br>' + data[i]['logs']['monitor'] + '<p>'
        }
        $('#debug').html(content.replace(/\\n\\n/g, '<br>').replace(/\\n/g, ''))
	});
}

function human_time(UNIX_timestamp){
    if (isNaN(parseFloat(UNIX_timestamp))) {
        return UNIX_timestamp
    }
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    dt = new Date(Math.round(parseFloat(UNIX_timestamp * 1000)))
    year = dt.getFullYear()
    month = months[dt.getMonth()]
    date = dt.getDate()
    hour = dt.getHours()
    min = dt.getMinutes()
    sec = dt.getSeconds()
    if (hour < 10) hour = '0' + hour
    if (min < 10) min = '0' + min
    if (sec < 10) sec = '0' + sec
    return date + ' ' + month + ' ' + year + ' ' + hour + ':' + min + ':' + sec
}


function show_test_run_info(trid) {
     $.getJSON("/_test_info", {"trid": trid}, function(data) {
            content = $("#testrun-" + trid).html()
            if (content == '') {
                if (data.description) {
                    content += '<pre><code>' + data.description + '</code></pre>'
                } else {content += 'No description found for TestRun ' + trid}
            } else {content = ''}
            $("#testrun-" + trid).html(content);
          });  // getJSON
 } // show_test_run_info()

