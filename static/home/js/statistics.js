/*global nv,d3,data_cryst_year_container,data_unique_class_cryst_container,data_unique_class_cryst_year_container,data_cryst_class_year_container,data_unique_cryst_container,data_unique_cryst_year_container*/

 function mergeSVG(div) {
     let SVG = $("#"+div).find("svg")[0];
     let h = parseInt($(SVG).attr("height"), 10);
     let w = parseInt($(SVG).attr("width"), 10);
     let legend = $("#legend").find("svg")[0];
     let h2 = parseInt($(legend).attr("height"), 10);
     let w2 = parseInt($(legend).attr("width"), 10);
     let leg_w = (w-w2)/2;
     SVG.setAttribute("height", (h + h2));
     if (w2 > w) {
         SVG.setAttribute("width", (w2));
         leg_w = 0
         //svg_w = Math.abs(w-w2)/2
     } else {
         leg_w = Math.abs(w-w2)/2
         //svg_w = 0
     }
     for (let i = 0; i < legend.children.length; i++) {
         legend.children[i].setAttribute("transform", "translate ("+leg_w.toString()+" " + h.toString()+")");
         $(SVG).append(legend.children[i]);
     }
 }

 function clear_all() {
     $("#charts").find(".chart_type").each(function () {
         $(this).find("span:first").css("background", "white");
     });
     $("#charts").find(".chart_container").each(function () {
         $(this).css("display", "none");
     });
 }

function move_legend_into_whitespace(parent_svg, offset_x=0, offset_y=0)
{
    //The usual methods for obtaining the size of the SVG bounding box do not work correctly 
    // because the SVG container has a display type of hidden. 
    // So this hack obtains the offset applied to the right aligned y-axis as the basis for the legend positioning.
    let yAxis_transform = parent_svg.select(".nv-y").attr("transform"); 
    yAxis_transform.replace(/translate\((\d+),\s*\d+\)/, function(match, p1, p2) {
        offset_x = offset_x + parseInt(p1, 10);         
    });

    let legend = parent_svg.select(".nv-legendWrap");
    if (!legend.empty()) {
        legend.selectAll(".nv-series").each(function(d, i) {
            d3.select(this).attr("transform", "translate(0," + (i * 20) + ")");
        });
        parent_svg.node().appendChild(legend.node());
        legend.attr("transform", "translate(" + offset_x + "," + offset_y + ")");
}}

function rotate_x_labels(parent_svg, angle=-45, x_offset, y_offset)
{
    let xAxis = parent_svg.select(".nv-x");
    if (!xAxis.empty()) {
        xAxis.selectAll(".tick").each(function(d, i) {
            d3.select(this).select('text').attr("transform", "rotate(" + angle + ",0,0)translate(" + y_offset + "," + x_offset + ")");
        });
        
        
}}

function convert_gridlines_to_axis_ticks(parent_svg, tick_length=10)
{
    //Shrink the gridlines and make them look like ticks.
    let xAxis = parent_svg.select(".nv-x");
    if (!xAxis.empty()) {
        xAxis.selectAll(".tick").each(function(d, i) {
            d3.select(this).select('line').attr("y2", tick_length).classed("darktick", true);
        });
    }

    let yAxis = parent_svg.select(".nv-y");
    if (!yAxis.empty()) {
        yAxis.selectAll(".tick").each(function(d, i) {
            d3.select(this).select('line').attr("x2", tick_length).classed("darktick", true);
        });
    }
}

function add_whitebackground_to_svg(parent_svg)
{
  parent_svg.insert("rect", ":first-child")
  .attr('width', '100%')
  .attr('height', '100%')
  .attr('fill', '#ffffff')
}

function initialiseChart()
{
    var chart = nv.models.multiBarChart()
        .reduceXTicks(false)
        .stacked(true)
        .showControls(false)
        .margin({ top: 30, right: 210, bottom: 40, left: 20 })
        .color(d3.scale.category20().range())
        .rightAlignYAxis(true);
    chart.yAxis
        .tickFormat(d3.format(",f"))
        .showMaxMin(false);

    return chart;
}

append_chart_to_container = function(chart, datum, svg) {            
    svg
        .datum(datum)
        //.transition().duration(500)
        .call(chart);
}

function attachPlot(data, svg_selector, legend_x_offset, legend_y_offset)
{
    let svg = d3.select(svg_selector);
    let chart = initialiseChart()
     chart.dispatch.on('renderEnd', function() {
        convert_gridlines_to_axis_ticks(svg, 3);
    });
    append_chart_to_container(chart, data, svg);              
    move_legend_into_whitespace(svg, legend_x_offset, legend_y_offset);
    rotate_x_labels(svg, -45, 0, -18);
    // Quality of life improvement for downloads so background is not transparent
    add_whitebackground_to_svg(svg);
}

 $(window).on("load", function () {
    //Unique crystallized receptors graph
    if (typeof chemotype__distinct_structure__data != "undefined"){
      nv.addGraph(function () {
        //By chemotype - number of unique structures
        attachPlot(chemotype__distinct_structure__data, "#chemotype__distinct_structure__container svg", 40, 30);
      });

      nv.addGraph(function () {
        //By chemotype - number of unique GPCR-ligand complex structures
        attachPlot(chemotype__distinct_gpcrligand__data, "#chemotype__distinct_gpcrligand__container svg", 40, 30); 
      });
      
      nv.addGraph(function () {
        //By chemotype - total number of unique structures including redundant structures
        attachPlot(chemotype__all_structures__data, "#chemotype__all_structures__container svg", 60, 30);
      });
      
      nv.addGraph(function () {
        //By class - number of unique structures
        attachPlot(class__distinct_structure__data, "#class__distinct_structure__container svg", -60, 30);
      });
     
      nv.addGraph(function () {
        //By class - number of unique GPCR-ligand complex structures
        attachPlot(class__distinct_gpcrligand__data, "#class__distinct_gpcrligand__container svg", -60, 30);
      });
      
      nv.addGraph(function () {
        //By class - total number of unique structures including redundant structures
        attachPlot(class__all_structures__data, "#class__all_structures__container svg", -50, 30);
      });

      $(".chart_type").click(function () {
          clear_all();
          $(this).find("span:first").css("background", "black");
          let point = $("#" + $(this).attr("id")).find("svg");
          $(point).css("visibility", "hidden");
          $("#"+$(this).attr("id") + ".chart_container").css("display", "");
      });

      $(document).ready(function () {
          $("#class__distinct_structure.chart_container").css("display", "");
      });

      populateChartCategoryDropdowns(class__all_structures__data.map( x => x.key), chemotype__all_structures__data.map( x => x.key));
    }
});

function populateChartCategoryDropdowns(class_list, chemotype_list) {
    $('categoryDropdownButtonList')
}
