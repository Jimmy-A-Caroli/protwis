/**
 * compoundPreviewTooltip.js (v2.0)
 *
 * This module provides a tooltip for chemical structures. It now supports both
 * small molecules (via SMILES and OpenChemLib) and peptides (via sequences and PeptideLayoutEngine).
 *
 * It binds a hover event to elements matching the provided selector (e.g., "a.struct").
 * The tooltip's content is determined by the element's data attributes:
 *
 *  - For Peptides:
 *    - It looks for `data-ligand-type="peptide"` and a `data-sequence` attribute.
 *    - If found, it uses PeptideLayoutEngine to render a snake-like diagram.
 *
 *  - For Small Molecules:
 *    - It checks `rel="Generate_from_SMILES"` and a `data-smiles` attribute.
 *    - If found, it uses OpenChemLib (OCL) to generate an SVG.
 *
 *  - Fallbacks:
 *    - If `rel` contains an image URL, it displays that image.
 *    - Otherwise, it displays a default "No image available" picture.
 *
 * Usage:
 *   compoundPreview("a.struct");
 *
 * Dependencies:
 *   - jQuery
 *   - OpenChemLib (OCL) - must be loaded if SMILES rendering is needed.
 *   - PeptideLayoutEngine - must be loaded if peptide rendering is needed.
 *
 * Note:
 *   - Ensure that window.NO_IMAGE_URL is defined in your HTML.
 *   - The anchor tags in your table should have the following data attributes:
 *     - For peptides: `data-ligand-type="peptide" data-sequence="..."`
 *     - For small molecules: `rel="Generate_from_SMILES" data-smiles="..."`
 */
function compoundPreview(selector = "a.struct", noImageUrl = window.NO_IMAGE_URL) {
    if (!noImageUrl) {
        noImageUrl = "/static/home/images/No_image_available.svg";
    }
    const xOffset = 30, yOffset = -10;

    // Use event delegation for better performance with DataTables
    // This binds one event listener to the body, instead of one for each link.
    $('body').on('mouseenter', selector, function(e) {
        let $link = $(this);
        let tooltipHtml = "";

        // --- NEW LOGIC: Check ligand type first ---
        const ligandType = $link.data('ligand-type');

        if (ligandType === 'peptide') {
            const sequence = $link.data('sequence');
            if (sequence && typeof PeptideLayoutEngine !== 'undefined') {
                try {
                    // It's a peptide! Use our new engine.
                    const peptideDrawer = new PeptideLayoutEngine({
                        // Settings optimized for a small tooltip
                        residueRadius: 16,
                        overlapAmount: 6,
                        padding: 10,
                        fontSize: 12,
                        residuesPerRow: 10,
                        maxLength: 50,
                        rowSpacingFactor: 1.5
                    });
                    const svgElement = peptideDrawer.generateSvgElement(sequence);
                    if (svgElement) {
                        tooltipHtml = svgElement.outerHTML;
                    } else {
                        tooltipHtml = "<div>Peptide sequence empty</div>";
                    }
                } catch(err) {
                    console.error("PeptideLayoutEngine error:", err);
                    tooltipHtml = "<div>Error rendering peptide</div>";
                }
            } else {
                tooltipHtml = `<img style="max-width: 200px; height: auto" src="${noImageUrl}" />`;
            }
        } else {
            // --- ORIGINAL LOGIC for small molecules and other fallbacks ---
            let fallbackUrl = $link.attr("rel");
            let smiles = $link.data("smiles") || "";

            if (fallbackUrl === "Generate_from_SMILES" && smiles && typeof OCL !== 'undefined') {
                try {
                    let mol = OCL.Molecule.fromSmiles(smiles);
                    mol.inventCoordinates();
                    const svgSize = 200;
                    const svgOptions = {
                        autoCrop: true, noStereoProblem: true,
                        suppressChiralText: true, suppressCIPParity: true, suppressESR: true,
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
        }
        
        // Create and position the tooltip
        $("body").append(`<p class="tooltip-struct">${tooltipHtml}</p>`);
        $(".tooltip-struct")
            .css({ top: e.pageY - yOffset + "px", left: e.pageX + xOffset + "px" })
            .fadeIn("fast");
            
    }).on('mouseleave', selector, function() {
        $(".tooltip-struct").remove();
    }).on('mousemove', selector, function(e) {
        $(".tooltip-struct").css({ top: e.pageY - yOffset + "px", left: e.pageX + xOffset + "px" });
    });
}