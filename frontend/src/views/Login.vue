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
        <button type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
      </form>
      <div class="tips">
        <div>管理员: admin / admin123</div>
        <div>使用者: user / user123</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { login } from '../api'

const router = useRouter()
const route = useRoute()
const username = ref('admin')
const password = ref('admin123')
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  loading.value = true
  error.value = ''
  try {
    const res = await login(username.value, password.value)
    localStorage.setItem('token', res.token)
    localStorage.setItem('user', JSON.stringify(res.user))
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

.tips {
  margin-top: 18px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.7;
  text-align: center;
}
</style>
