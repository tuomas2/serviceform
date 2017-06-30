default: image

base:
	@docker build -f Dockerfile-base \
	    --build-arg VCS_REF=`git rev-parse --short HEAD` \
	    --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"` \
	    --build-arg VERSION=`python setup.py --version` \
	    -t tuomasairaksinen/serviceform-base:latest \
     .
image: base
	@docker build \
	    --build-arg VCS_REF=`git rev-parse --short HEAD` \
	    --build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"` \
	    --build-arg VERSION=`python setup.py --version` \
	    -t tuomasairaksinen/serviceform:latest \
     .
