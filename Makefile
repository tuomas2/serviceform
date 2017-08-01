default: image
all: base image
push: push-image

base:
	@docker build -f Dockerfile-base \
	    --build-arg VCS_REF=`git rev-parse --short HEAD` \
	    --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"` \
	    --build-arg VERSION=`python setup.py --version` \
	    -t tuomasairaksinen/serviceform-base:latest \
     .
image:
	@docker build \
	    --build-arg VCS_REF=`git rev-parse --short HEAD` \
	    --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"` \
	    --build-arg VERSION=`python setup.py --version` \
	    -t tuomasairaksinen/serviceform:latest \
     .
push-base:
	@docker push tuomasairaksinen/serviceform-base:latest
push-image:
	@docker push tuomasairaksinen/serviceform:latest
