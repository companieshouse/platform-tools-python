artifact_name       := concourse_webhook_validator

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

.PHONY: all
all: build

.PHONY: clean
clean:
	rm -f ./*.tar.gz
	rm -rf ./dist/ ./src/*.egg-info/

.PHONY: build
build:
	sed -i '' -e "s/^version\ =\ .*/version\ =\ \"$(version)\"/" pyproject.toml
	$(python_bin) -m build
	cp ./dist/$(artifact_name)-$(version)* ./

.PHONY: dist
dist: clean build
