artifact_name       := ec2_tag_query
version             := $(shell grep "version" pyproject.toml | awk '{print $3}' | cut -d\" -f2)

.PHONY: all
all: build

.PHONY: clean
clean:
	rm -f ./*.tar.gz
	rm -rf ./dist/ ./src/*.egg-info/

.PHONY: build
build:
	python3 -m build
	cp ./dist/$(artifact_name)-$(version).tar.gz ./$(artifact_name)-$(version).tar.gz

.PHONY: dist
dist: clean build
