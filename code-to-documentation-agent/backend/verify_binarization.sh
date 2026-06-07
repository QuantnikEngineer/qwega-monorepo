#!/bin/bash
set -e

echo "🔍 Verifying Binarized Backend Build"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="agent-documentation-backend:binarized"
CONTAINER_NAME="agent-doc-backend-test"
PORT=8000

echo -e "${YELLOW}📦 Building Docker image...${NC}"
docker build -f Dockerfile.binarized -t $IMAGE_NAME .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Build successful!${NC}"
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}🔎 Checking image size...${NC}"
docker images $IMAGE_NAME --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

echo ""
echo -e "${YELLOW}🚀 Starting container...${NC}"
docker run -d --name $CONTAINER_NAME -p $PORT:$PORT \
    -e BUILDAI_BACKEND_API_URL="${BUILDAI_BACKEND_API_URL:-http://dummy-api.local}" \
    -e AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-dummy}" \
    -e AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-https://dummy.openai.azure.com}" \
    -e CLOUD_PROVIDER="${CLOUD_PROVIDER:-azure}" \
    $IMAGE_NAME

# Wait for container to start
sleep 5

echo ""
echo -e "${YELLOW}📊 Checking container status...${NC}"
docker ps --filter name=$CONTAINER_NAME

echo ""
echo -e "${YELLOW}📝 Container logs (last 20 lines):${NC}"
docker logs --tail 20 $CONTAINER_NAME

echo ""
echo -e "${YELLOW}🧪 Testing health endpoint...${NC}"
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/docs || echo "000")

if [ "$HEALTH_CHECK" = "200" ]; then
    echo -e "${GREEN}✅ Health check passed! API is responding on port $PORT${NC}"
    echo -e "${GREEN}📖 API docs available at: http://localhost:$PORT/docs${NC}"
else
    echo -e "${RED}❌ Health check failed! HTTP status: $HEALTH_CHECK${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Verifying binary exists in container...${NC}"
docker exec $CONTAINER_NAME ls -lh /app/agent-documentation-backend

echo ""
echo -e "${YELLOW}🔍 Checking for required data files...${NC}"
echo "Checking vertexai.json:"
docker exec $CONTAINER_NAME ls -la /app/vertexai.json 2>/dev/null && echo "✅ Found" || echo "⚠️  Not found (optional)"

echo ""
echo -e "${GREEN}✨ Verification complete!${NC}"
echo ""
echo "To stop and remove the test container:"
echo "  docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
echo ""
echo "To run the container with your own environment:"
echo "  docker run -p $PORT:$PORT \\"
echo "    -e BUILDAI_BACKEND_API_URL=\$BUILDAI_BACKEND_API_URL \\"
echo "    -e AZURE_OPENAI_API_KEY=\$AZURE_OPENAI_API_KEY \\"
echo "    -e AZURE_OPENAI_ENDPOINT=\$AZURE_OPENAI_ENDPOINT \\"
echo "    -e AWS_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID \\"
echo "    -e AWS_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY \\"
echo "    -e CLOUD_PROVIDER=\$CLOUD_PROVIDER \\"
echo "    $IMAGE_NAME"
