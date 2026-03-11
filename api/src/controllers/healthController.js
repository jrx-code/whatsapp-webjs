const fsp = require('fs').promises
const qrcode = require('qrcode-terminal')
const { sessionFolderPath } = require('../config')
const { sendErrorResponse } = require('../utils')
const { logger } = require('../logger')
const { sessions, validateSession } = require('../sessions')

/**
 * Responds to request with 'pong'
 *
 * @function ping
 * @async
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @returns {Promise<void>} - Promise that resolves once response is sent
 * @throws {Object} - Throws error if response fails
 */
const ping = async (req, res) => {
  /*
    #swagger.tags = ['Various']
    #swagger.summary = 'Health check'
    #swagger.description = 'Responds to request with "pong" message'
    #swagger.responses[200] = {
      description: "Response message",
      content: {
        "application/json": {
          example: {
            success: true,
            message: "pong"
          }
        }
      }
    }
  */
  res.json({ success: true, message: 'pong' })
}

/**
 * Example local callback that generates a QR code and writes a log file
 *
 * @function localCallbackExample
 * @async
 * @param {Object} req - Express request object containing a body object with dataType and data
 * @param {string} req.body.dataType - Type of data (in this case, 'qr')
 * @param {Object} req.body.data - Data to generate a QR code from
 * @param {Object} res - Express response object
 * @returns {Promise<void>} - Promise that resolves once response is sent
 * @throws {Object} - Throws error if response fails
 */
const localCallbackExample = async (req, res) => {
  /*
    #swagger.tags = ['Various']
    #swagger.summary = 'Local callback'
    #swagger.description = 'Used to generate a QR code and writes a log file. ONLY FOR DEVELOPMENT/TEST PURPOSES.'
    #swagger.responses[200] = {
      description: "Response message",
      content: {
        "application/json": {
          example: {
            success: true
          }
        }
      }
    }
  */
  try {
    const { dataType, data } = req.body
    if (dataType === 'qr') { qrcode.generate(data.qr, { small: true }) }
    await fsp.mkdir(sessionFolderPath, { recursive: true })
    const logPath = `${sessionFolderPath}/message_log.txt`
    // Rotate log file if it exceeds 10MB
    try {
      const stat = await fsp.stat(logPath).catch(() => null)
      if (stat && stat.size > 10 * 1024 * 1024) {
        await fsp.rename(logPath, `${logPath}.old`).catch(() => {})
      }
    } catch { /* ignore rotation errors */ }
    await fsp.writeFile(logPath, `${JSON.stringify(req.body)}\r\n`, { flag: 'a+' })
    res.json({ success: true })
  } catch (error) {
    /* #swagger.responses[500] = {
      description: "Server Failure.",
      content: {
        "application/json": {
          schema: { "$ref": "#/definitions/ErrorResponse" }
        }
      }
    }
    */
    logger.error(error, 'Failed to handle local callback')
    sendErrorResponse(res, 500, error.message)
  }
}

/**
 * Deep health check — verifies server AND session connectivity
 * Returns 200 if at least one session is CONNECTED, 503 if none are
 *
 * @function healthz
 * @async
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @returns {Promise<void>}
 */
const healthz = async (req, res) => {
  try {
    const sessionList = []
    let anyConnected = false

    for (const [sessionId] of sessions) {
      try {
        const validation = await validateSession(sessionId)
        sessionList.push({ sessionId, state: validation.state, connected: validation.success })
        if (validation.success) anyConnected = true
      } catch {
        sessionList.push({ sessionId, state: null, connected: false })
      }
    }

    const status = sessions.size === 0 ? 200 : (anyConnected ? 200 : 503)
    res.status(status).json({
      success: anyConnected || sessions.size === 0,
      sessions: sessionList,
      totalSessions: sessions.size,
      connectedSessions: sessionList.filter(s => s.connected).length
    })
  } catch (error) {
    logger.error(error, 'Health check failed')
    res.status(503).json({ success: false, error: error.message })
  }
}

module.exports = { ping, localCallbackExample, healthz }
