/**
 * Client-side RSA-OAEP (SHA-256) password encryption for login / password APIs.
 * Passwords are never sent as plaintext JSON fields.
 */

let cachedPem = null
let cachedKey = null

function pemToArrayBuffer(pem) {
  const b64 = pem
    .replace(/-----BEGIN PUBLIC KEY-----/g, '')
    .replace(/-----END PUBLIC KEY-----/g, '')
    .replace(/\s+/g, '')
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

function bufferToBase64(buf) {
  const bytes = new Uint8Array(buf)
  let s = ''
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i])
  return btoa(s)
}

async function importPublicKey(pem) {
  const key = await crypto.subtle.importKey(
    'spki',
    pemToArrayBuffer(pem),
    { name: 'RSA-OAEP', hash: 'SHA-256' },
    false,
    ['encrypt'],
  )
  return key
}

/**
 * Fetch server public key (or use cache) and encrypt a password string.
 * @returns {Promise<string>} base64 ciphertext for password_encrypted field
 */
export async function encryptPassword(password, publicKeyPem) {
  if (!password) throw new Error('密码不能为空')
  if (!window.crypto?.subtle) {
    throw new Error('当前浏览器不支持 Web Crypto，无法安全加密密码')
  }
  let pem = publicKeyPem || cachedPem
  let key = cachedKey
  if (!pem || !key) {
    throw new Error('缺少服务端公钥，请刷新页面后重试')
  }
  if (publicKeyPem && publicKeyPem !== cachedPem) {
    pem = publicKeyPem
    key = await importPublicKey(pem)
    cachedPem = pem
    cachedKey = key
  }
  const encoded = new TextEncoder().encode(password)
  const cipher = await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, key, encoded)
  return bufferToBase64(cipher)
}

/**
 * Load and cache the backend RSA public key.
 */
export async function loadPublicKey(fetcher) {
  const res = await fetcher()
  const pem = res.public_key_pem || res.publicKeyPem
  if (!pem) throw new Error('服务端未返回公钥')
  cachedPem = pem
  cachedKey = await importPublicKey(pem)
  return pem
}

export function clearKeyCache() {
  cachedPem = null
  cachedKey = null
}
