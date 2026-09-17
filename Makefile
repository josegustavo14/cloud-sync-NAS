.PHONY: test lint build
test:
	.venv/bin/pytest -q
	npm --prefix frontend test
	cd android_app && flutter test
lint:
	npm --prefix frontend run lint
	cd android_app && flutter analyze
build:
	npm --prefix frontend run build
	docker build -t personal-cloud-sync:dev .
