artifact_name       := ebs_recover_and_replace

ifdef VERSION
version := $(VERSION)
else
$(error Environment variable VERSION is not set)
endif

ifdef PYTHON_BIN
python_bin := $(PYTHON_BIN)
else
python_bin := python3
endif

uname := $(shell uname)
ifeq ($(UNAME), Darwin)
sed_opts := "-i ''"
else
sed_opts := "-i"
endif

.PHONY: all
all: build

.PHONY: clean
clean:
	rm -f ./*.tar.gz ./*.whl
	rm -rf ./dist/ ./src/*.egg-info/

.PHONY: build
build:
	sed $(sed_opts) -e "s/^version\ =\ .*/version\ =\ \"$(version)\"/" pyproject.toml
	$(python_bin) -m build
	cp ./dist/$(artifact_name)-$(version)* ./

.PHONY: dist
dist: clean build
