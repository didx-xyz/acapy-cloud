#!/bin/bash

ECR_REGISTRY=""

# get parameters
while getopts v: flag
do
  case "${flag}" in
    v) ECR_REGISTRY=${OPTARG};;
  esac
done


for r in $(grep 'image: \${ECR_REGISTRY}' docker-compose.yml | sed -e 's/^.*\///')
do
  aws ecr create-repository --repository-name "$r"
done
