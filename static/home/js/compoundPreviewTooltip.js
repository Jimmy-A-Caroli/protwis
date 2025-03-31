/**
 * compoundPreviewTooltip.js
 *
 * This module provides the compoundPreview function which binds a tooltip behavior
 * to elements (by default "a.struct") displaying a ligand's structure preview.
 * 
 * When a user hovers over a ligand link, the tooltip is dynamically created:
 *  - If the element's "rel" attribute is "Generate_from_SMILES" and a valid SMILES string is provided,
 *    the function uses OpenChemLib (OCL) to generate an SVG of the molecule.
 *  - If the "rel" attribute contains a fallback image URL (and is not "Not_available"),
 *    it displays that image.
 *  - Otherwise, it displays a default "No image available" picture.
 *
 * The tooltip is positioned relative to the mouse cursor, and updates its position on mousemove.
 * It is removed when the mouse leaves the element.
 *
 * Usage:
 *   compoundPreview("a.struct"); // Binds the tooltip to all anchor elements with the "struct" class.
 *
 * Dependencies:
 *   - jQuery
 *   - OpenChemLib (OCL)
 *
 * Note: Ensure that window.NO_IMAGE_URL is defined in your HTML before loading this script.
 */
function compoundPreview(selector = "a.struct", noImageUrl = window.NO_IMAGE_URL) {
    const xOffset = 30, yOffset = -10;
    $(selector).hover(
        function(e) {
            let $link = $(this);
            let fallbackUrl = $link.attr("rel"); // "Generate_from_SMILES" or "Not_available"
            let smiles = $link.data("smiles") || "";
            let tooltipHtml = "";
            if (fallbackUrl === "Generate_from_SMILES" && smiles) {
                try {
                    let mol = OCL.Molecule.fromSmiles(smiles);
                    mol.inventCoordinates();
                    const svgSize = 200;
                    const svgOptions = {
                        autoCrop: true,
                        noStereoProblem: true,
                        suppressChiralText: true,
                        suppressCIPParity: true,
                        suppressESR: true,
                    };
                    tooltipHtml = mol.toSVG(svgSize, svgSize, null, svgOptions);
                } catch (err) {
                    console.error("OCL error:", err);
                    tooltipHtml = "<div>Invalid SMILES</div>";
                }
            } else if (fallbackUrl && fallbackUrl !== "Not_available") {
                tooltipHtml = `<img style="max-width: 200px; height: auto" src="${fallbackUrl}" />`;
            } else {
                tooltipHtml = `<img style="max-width: 200px; height: auto" src="${noImageUrl}" />`;
            }

            $("body").append(`<p class="tooltip-struct">${tooltipHtml}</p>`);
            $(".tooltip-struct")
              .css({ top: e.pageY - yOffset + "px", left: e.pageX + xOffset + "px" })
              .fadeIn("fast");
        },
        function() {
            $(".tooltip-struct").remove();
        }
    );
    $(selector).mousemove(function(e) {
        $(".tooltip-struct").css({ top: e.pageY - yOffset + "px", left: e.pageX + xOffset + "px" });
    });
}