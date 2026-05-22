FROM node:20-alpine

WORKDIR /app

# Copy dependency configs
COPY package.json package-lock.json ./

# Install packages
RUN npm install

# Copy application source code
COPY . .

EXPOSE 3000

# Start dev server
CMD ["npm", "run", "dev"]
