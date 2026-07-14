<template>
  <div class="page">
    <div class="card">
      <div class="head">
        <h2>安全管理</h2>
        <p class="sub">修改当前登录账号的密码。密码经 RSA-OAEP 加密后传输。</p>
      </div>

      <div class="form">
        <label>
          当前用户
          <input :value="username" type="text" disabled />
        </label>
        <label>
          原密码
          <input v-model="form.oldPwd" type="password" autocomplete="current-password" />
        </label>
        <label>
          新密码
          <input v-model="form.newPwd" type="password" autocomplete="new-password" placeholder="至少 6 位" />
        </label>
        <label>
          确认新密码
          <input v-model="form.confirm" type="password" autocomplete="new-password" />
        </label>

        <p v-if="msg" class="msg" :class="{ err: isError }">{{ msg }}</p>

        <button type="button" class="btn primary" :disabled="saving" @click="submit">
          {{ saving ? '提交中...' : '更新密码' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { changePassword, getAuthPublicKey } from '../api'
import { encryptPassword, loadPublicKey } from '../utils/crypto'

const user = JSON.parse(localStorage.getItem('user') || '{}')
const username = computed(() => user.username || user.display_name || '—')
const form = reactive({ oldPwd: '', newPwd: '', confirm: '' })
const saving = ref(false)
const msg = ref('')
const isError = ref(false)

async function submit() {
  msg.value = ''
  isError.value = false
  if (!form.oldPwd || !form.newPwd) {
    isError.value = true
    msg.value = '请填写原密码与新密码'
    return
  }
  if (form.newPwd.length < 6) {
    isError.value = true
    msg.value = '新密码至少 6 位'
    return
  }
  if (form.newPwd !== form.confirm) {
    isError.value = true
    msg.value = '两次输入的新密码不一致'
    return
  }
  saving.value = true
  try {
    await loadPublicKey(getAuthPublicKey)
    const old_password_encrypted = await encryptPassword(form.oldPwd)
    const new_password_encrypted = await encryptPassword(form.newPwd)
    await changePassword({ old_password_encrypted, new_password_encrypted })
    msg.value = '密码已更新'
    form.oldPwd = ''
    form.newPwd = ''
    form.confirm = ''
  } catch (e) {
    isError.value = true
    msg.value = e.message || '修改失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.page {
  height: 100%;
  overflow: auto;
  padding: 28px 32px;
}

.card {
  max-width: 480px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 28px 32px;
}

.head {
  margin-bottom: 24px;
}

h2 {
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.sub {
  margin-top: 8px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

input {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 11px 12px;
  font-size: 15px;
  color: var(--text);
  background: #fff;
}

input:disabled {
  background: #f7f7f8;
  color: var(--text-secondary);
}

.btn {
  margin-top: 8px;
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 10px;
  padding: 11px 16px;
  font-size: 14px;
  cursor: pointer;
}

.btn.primary {
  background: #111;
  color: #fff;
  border-color: #111;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.msg {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 10px 12px;
  background: #fafafa;
  border-radius: 8px;
}

.msg.err {
  color: #a33;
  background: #faf5f5;
}
</style>
