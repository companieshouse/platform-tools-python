artifact_name       := ec2_tag_query
version             := $(shell grep "version" pyproject.toml | awk '{print $3}' | cut -d\" -f2)

ifdef PYTHON_BIN
python_bin := $(PYTHON_BIN)
else
python_bin := python3
endif

.PHONY: all
all: build

.PHONY: clean
clean:
	rm -f ./*.tar.gz
	rm -rf ./dist/ ./src/*.egg-info/

.PHONY: build
build:
	$(python_bin) -m build
	cp ./dist/$(artifact_name)-$(version).tar.gz ./$(artifact_name)-$(version).tar.gz

.PHONY: dist
dist: clean build
