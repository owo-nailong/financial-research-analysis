<template>
  <div class="admin-page">
    <section class="card">
      <h3>系统状态</h3>
      <pre>{{ healthText }}</pre>
      <button type="button" class="btn" @click="loadHealth">刷新</button>
      <button type="button" class="btn" @click="reseed">重新注入种子数据</button>
    </section>

    <section class="card">
      <h3>用户管理（管理员）</h3>
      <table>
        <thead>
          <tr><th>用户名</th><th>角色</th><th>显示名</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.username">
            <td>{{ u.username }}</td>
            <td>{{ u.role }}</td>
            <td>{{ u.display_name }}</td>
          </tr>
        </tbody>
      </table>
      <div class="form">
        <input v-model="form.username" placeholder="新用户名" />
        <input v-model="form.password" placeholder="密码" type="password" />
        <select v-model="form.role">
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <button type="button" class="btn primary" @click="addUser">创建用户</button>
      </div>
      <p v-if="msg" class="msg">{{ msg }}</p>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { healthCheck, listUsers, createUser } from '../api'

const healthText = ref('')
const users = ref([])
const msg = ref('')
const form = ref({ username: '', password: '', role: 'user' })

async function loadHealth() {
  try {
    const h = await healthCheck()
    healthText.value = JSON.stringify(h, null, 2)
  } catch (e) {
    healthText.value = e.message
  }
}

async function loadUsers() {
  try {
    const res = await listUsers()
    users.value = res.data || []
  } catch (e) {
    msg.value = e.message
  }
}

async function addUser() {
  try {
    await createUser(form.value)
    msg.value = '创建成功'
    form.value = { username: '', password: '', role: 'user' }
    await loadUsers()
  } catch (e) {
    msg.value = e.message
  }
}

async function reseed() {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.post('/api/admin/seed?force=true', null, {
      headers: { Authorization: `Bearer ${token}` },
    })
    msg.value = '种子数据完成: ' + JSON.stringify(res.data)
    await loadHealth()
  } catch (e) {
    msg.value = e.message
  }
}

onMounted(async () => {
  await loadHealth()
  await loadUsers()
})
</script>

<style scoped>
.admin-page {
  height: 100%;
  overflow: auto;
  padding: 20px 24px;
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr 1fr;
}

.card {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px;
  background: #fff;
}

h3 {
  margin-bottom: 12px;
  font-size: 15px;
}

pre {
  background: #fafafa;
  border-radius: 8px;
  padding: 12px;
  font-size: 12px;
  max-height: 320px;
  overflow: auto;
  margin-bottom: 12px;
}

.btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 8px 12px;
  margin-right: 8px;
  cursor: pointer;
  font-size: 13px;
}

.btn.primary {
  background: #111;
  color: #fff;
  border-color: #111;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 12px;
}

th,
td {
  border-bottom: 1px solid var(--border);
  padding: 8px;
  text-align: left;
}

.form {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.form input,
.form select {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
}

.msg {
  margin-top: 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .admin-page {
    grid-template-columns: 1fr;
  }
}
</style>
