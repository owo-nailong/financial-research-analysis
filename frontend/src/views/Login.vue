<template>
  <div class="login-page">
    <div class="card">
      <h1>智研AI</h1>
      <p class="sub">金融研报智能分析与投资决策辅助系统</p>
      <form @submit.prevent="onSubmit">
        <label>
          用户名
          <input v-model="username" autocomplete="username" required />
        </label>
        <label>
          密码
          <input v-model="password" type="password" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <p class="secure-tip">密码经 RSA-OAEP 加密后传输，不以明文提交</p>
        <button type="submit" :disabled="loading || !keyReady">
          {{ loading ? '登录中...' : keyReady ? '登录' : '准备加密通道...' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getAuthPublicKey, login } from '../api'
import { encryptPassword, loadPublicKey } from '../utils/crypto'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const keyReady = ref(false)

onMounted(async () => {
  try {
    await loadPublicKey(getAuthPublicKey)
    keyReady.value = true
  } catch (e) {
    error.value = e.message || '无法获取加密公钥'
  }
})

async function onSubmit() {
  loading.value = true
  error.value = ''
  try {
    if (!keyReady.value) {
      await loadPublicKey(getAuthPublicKey)
      keyReady.value = true
    }
    const passwordEncrypted = await encryptPassword(password.value)
    const res = await login(username.value.trim(), passwordEncrypted)
    localStorage.setItem('token', res.token)
    localStorage.setItem('user', JSON.stringify(res.user))
    password.value = ''
    router.replace(route.query.redirect || '/chat')
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f7f7f8;
}

.card {
  width: 380px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 36px 32px;
}

h1 {
  font-size: 24px;
  font-weight: 700;
  text-align: center;
}

.sub {
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  margin: 8px 0 24px;
}

label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 14px;
}

input {
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
}

button {
  width: 100%;
  margin-top: 8px;
  padding: 11px;
  border: none;
  border-radius: 8px;
  background: #111;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  color: #c44;
  font-size: 13px;
  margin-bottom: 8px;
}

.secure-tip {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0 0 4px;
  text-align: center;
}
</style>
