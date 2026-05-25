MAIN = main
PDF = $(MAIN).pdf

.PHONY: all clean

all: $(PDF)

$(PDF): $(MAIN).tex
	pdflatex -interaction=nonstopmode $(MAIN).tex
	pdflatex -interaction=nonstopmode $(MAIN).tex

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.pdf *.toc *.fls *.fdb_latexmk *.synctex.gz
