const app = require('./src/app')
const { servicePort, baseWebhookURL, enableWebHook, enableWebSocket, autoStartSessions } = require('./src/config')
const { logger } = require('./src/logger')
const { handleUpgrade } = require('./src/websocket')
const { restoreSessions, sessions, destroySession, validateSession } = require('./src/sessions')

// Check if BASE_WEBHOOK_URL environment variable is available when WebHook is enabled
if (!baseWebhookURL && enableWebHook) {
  logger.error('BASE_WEBHOOK_URL environment variable is not set. Exiting...')
  process.exit(1) // Terminate the application with an error code
}

const server = app.listen(servicePort, () => {
  logger.info(`Server running on port ${servicePort}`)
  logger.debug({ configuration: require('./src/config') }, 'Service configuration')
  if (autoStartSessions) {
    logger.info('Starting all sessions')
    restoreSessions()
  }
})

if (enableWebSocket) {
  server.on('upgrade', (request, socket, head) => {
    handleUpgrade(request, socket, head)
  })
}

// Graceful shutdown — close all browser sessions before exit
const gracefulShutdown = async (signal) => {
  logger.info(`Received ${signal}, shutting down gracefully...`)
  for (const [sessionId] of sessions) {
    try {
      logger.info({ sessionId }, 'Stopping session')
      await destroySession(sessionId)
    } catch (err) {
      logger.error({ sessionId, err }, 'Error stopping session during shutdown')
    }
  }
  server.close(() => {
    logger.info('HTTP server closed')
    process.exit(0)
  })
  // Force exit after 15 seconds
  setTimeout(() => {
    logger.warn('Forced shutdown after timeout')
    process.exit(1)
  }, 15000)
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'))
process.on('SIGINT', () => gracefulShutdown('SIGINT'))

// puppeteer uses subscriptions to SIGINT, SIGTERM, and SIGHUP to know when to close browser instances
// this disables the warnings when you starts more than 10 browser instances
process.setMaxListeners(0)
