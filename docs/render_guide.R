script_argument <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_argument) != 1) {
  stop("Run this script with Rscript docs/render_guide.R.")
}

script_path <- normalizePath(sub("^--file=", "", script_argument))
docs_dir <- dirname(script_path)
setwd(docs_dir)
guide_file <- "GUIDE_METHODOLOGIQUE_FR.md"

rmarkdown::render(
  guide_file,
  output_format = rmarkdown::pdf_document(
    latex_engine = "xelatex",
    toc = TRUE,
    number_sections = FALSE
  ),
  output_file = "GUIDE_METHODOLOGIQUE_FR.pdf",
  quiet = FALSE
)

rmarkdown::render(
  guide_file,
  output_format = rmarkdown::html_document(
    toc = TRUE,
    number_sections = FALSE,
    math_method = "mathjax"
  ),
  output_file = "GUIDE_METHODOLOGIQUE_FR.html",
  quiet = FALSE
)
