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

function move_legend_into_whitespace(parent_svg, offset_x=300, offset_y=0)
{        
        //move the legend up a parent level to the root <svg> so it can be positioned relative to svg within margin whitespace
        var legend = parent_svg.select(".nv-legendWrap");
        if (!legend.empty()) {            
            parent_svg.node().appendChild(legend.node());
            legend.attr("transform", "translate(" + offset_x + "," + offset_y + ")"); 
        }}

 $(window).on("load", function () {
    //Unique crystallized receptors graph
    if (typeof data_unique_cryst_container != "undefined"){
      nv.addGraph(function () {
          var datum = data_unique_cryst_container;
          var chart = nv.models.multiBarChart()
              .reduceXTicks(false)
              .stacked(true)
              .margin({ top: 100, right: 60, bottom: 20, left: 60 })
              .color(d3.scale.category20().range());
          chart.yAxis
              .tickFormat(d3.format(",f"))
              .showMaxMin(false);


          var yAxis2 = nv.models.axis()
              .scale(chart.yScale())
              .showMaxMin(false)
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum))
              .tickPadding(0)
              .orient("right");

        const svg = d3.select("#unique_cryst_container svg");
              
        svg
            .datum(datum)
            .transition().duration(500)
            .call(chart);
        
        svg
            .selectAll("g.nv-wrap.nv-multiBarWithLegend").append("g")
            .attr("class", "nv-y nv-axis")
            .attr("transform", "translate(780, 0)")
            .call(yAxis2);

        move_legend_into_whitespace(svg);

      });
      //Unique crystals/year
      nv.addGraph(function () {
          var datum = data_unique_cryst_year_container;
          var chart = nv.models.multiBarChart()
              .reduceXTicks(false)
              .stacked(true)
              .margin({ top: 100, right: 60, bottom: 20, left: 60 })
              .color(d3.scale.category20().range());
          chart.yAxis
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum));


          var yAxis2 = nv.models.axis()
              .scale(chart.yScale())
              .showMaxMin(false)
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum))
              .tickPadding(0)
              .orient("right");

          const svg = d3.select("#unique_cryst_year_container svg");

        svg
            .datum(datum)
            .transition().duration(500)
            .call(chart);
         
        svg
            .selectAll("g.nv-wrap.nv-multiBarWithLegend").append("g")
            .attr("class", "nv-y nv-axis")
            .attr("transform", "translate(780, 0)")
            .call(yAxis2);
        
        move_legend_into_whitespace(svg);

      });
      //All crystals/year
      nv.addGraph(function () {
          var chart = nv.models.multiBarChart()
              .reduceXTicks(false)
              .stacked(true)
              .margin({ top: 130, right: 60, bottom: 20, left: 60 })
              .color(d3.scale.category20().range());
          chart.yAxis
              .tickFormat(d3.format(",f"));

          var datum = data_cryst_year_container;

          var yAxis2 = nv.models.axis()
              .scale(chart.yScale())
              .showMaxMin(false)
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum))
              .tickPadding(0)
              .orient("right");

        const svg = d3.select("#cryst_year_container svg")

        svg
            .datum(datum)
            .transition().duration(500)
            .call(chart);
        svg
            .selectAll("g.nv-wrap.nv-multiBarWithLegend").append("g")
            .attr("class", "nv-y nv-axis")
            .attr("transform", "translate(780, 0)")
            .call(yAxis2);

        move_legend_into_whitespace(svg);

      });
      //Unique crystallized receptors per class graph
      nv.addGraph(function () {
          var datum = data_unique_class_cryst_container;
          var chart = nv.models.multiBarChart()
              .reduceXTicks(false)
              .stacked(true)
              .margin({ top: 100, right: 60, bottom: 20, left: 60 })
              .color(d3.scale.category20().range());
          chart.yAxis
              .tickFormat(d3.format(",f"))
              .showMaxMin(false);


          var yAxis2 = nv.models.axis()
              .scale(chart.yScale())
              .showMaxMin(false)
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum))
              .tickPadding(0)
              .orient("right");

        const svg = d3.select("#unique_cryst_class_container svg");

        svg
            .datum(datum)
            .transition().duration(500)
            .call(chart);
        svg
            .selectAll("g.nv-wrap.nv-multiBarWithLegend").append("g")
            .attr("class", "nv-y nv-axis")
            .attr("transform", "translate(780, 0)")
            .call(yAxis2);

        move_legend_into_whitespace(svg, x_offset=270);
      });
      //Unique crystals/year per class
      nv.addGraph(function () {
          var datum = data_unique_class_cryst_year_container;
          var chart = nv.models.multiBarChart()
              .reduceXTicks(false)
              .stacked(true)
              .margin({ top: 100, right: 60, bottom: 20, left: 60 })
              .color(d3.scale.category20().range());
          chart.yAxis
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum));


          var yAxis2 = nv.models.axis()
              .scale(chart.yScale())
              .showMaxMin(false)
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum))
              .tickPadding(0)
              .orient("right");

        const svg = d3.select("#unique_class_cryst_year_container svg");
        
        svg
            .datum(datum)
            .transition().duration(500)
            .call(chart);
        svg
        .selectAll("g.nv-wrap.nv-multiBarWithLegend").append("g")
        .attr("class", "nv-y nv-axis")
        .attr("transform", "translate(780, 0)")
        .call(yAxis2);

        move_legend_into_whitespace(svg, x_offset=270);
      });
      //All crystals/year per class
      nv.addGraph(function () {
          var chart = nv.models.multiBarChart()
              .reduceXTicks(false)
              .stacked(true)
              .margin({ top: 100, right: 60, bottom: 20, left: 60 })
              .color(d3.scale.category20().range());
          chart.yAxis
              .tickFormat(d3.format(",f"));

          var datum = data_cryst_class_year_container;

          var yAxis2 = nv.models.axis()
              .scale(chart.yScale())
              .showMaxMin(false)
              .tickFormat(d3.format(",f"))
              ._ticks(nv.utils.calcTicksY(400 / 36, datum))
              .tickPadding(0)
              .orient("right");

        const svg = d3.select("#cryst_class_year_container svg");

        svg
            .datum(datum)
            .transition().duration(500)
            .call(chart);
        
        svg
            .selectAll("g.nv-wrap.nv-multiBarWithLegend").append("g")
            .attr("class", "nv-y nv-axis")
            .attr("transform", "translate(780, 0)")
            .call(yAxis2);
        
        move_legend_into_whitespace(svg, x_offset=270);
      });

      $(".chart_type").click(function () {
          clear_all();
          $(this).find("span:first").css("background", "black");
          let point = $("#" + $(this).attr("id")).find("svg");
          $(point).css("visibility", "hidden");
          $("#"+$(this).attr("id") + ".chart_container").css("display", "");
      });

      $(document).ready(function () {
          $("#unique_class.chart_container").css("display", "");
      });
    }
});
