# oh-my-code

## backend

### 安装go环境

```shell
wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz
sudo tar -C /usr/local/ -xzf go1.21.6.linux-amd64.tar.gz
go mod init oh-my-code
go env -w GOPROXY=https://proxy.golang.com.cn,direct
go get github.com/gin-gonic/gin
go get github.com/lib/pq
```

### 安装数据库

选择Postgresql作为我们的数据库环境，然后使用如下配置文件启动容器：

```yaml
version: "3.1"
services:
  postgres:
    image: postgres:9.5
    container_name: postgres_db
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    volumes:
      - /home/ha/oh-my-code-data:/var/lib/postgresql/data
    ports:
      - 5432:5432
```

使用如下命令启动容器：

```shell
docker-compose up -d
```

启动后连接数据库并且创建表，如下命令所示：

```shell
psql -Upostgres -dpostgres -h localhost -p 5432
```

创建user_configs表，命令如下：

```sql
postgres=#create table user_configs(id int,username varchar,url varchar,port int,password varchar);
CREATE TABLE
postgres=# select * from user_configs;
 id | username | url | port | password 
----+----------+-----+------+----------
(0 rows)
```

### 编写后端代码

```go
package main

import (
	"database/sql"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
)

type UserConfig struct {
	ID       int    `json:"id"`
	Username string `json:"username"`
	URL      string `json:"url"`
	Port     int    `json:"port"`
	Password string `json:"password"`
}

var db *sql.DB

func main() {
	var err error

	// 连接到 PostgreSQL 数据库
	db, err = sql.Open("pgx", "host=localhost user=postgres password=postgres dbname=postgres")
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	// 创建 Gin 路由器
	router := gin.Default()

	// 获取所有用户配置
	router.GET("/user-configs", func(c *gin.Context) {
		rows, err := db.Query("SELECT * FROM user_configs")
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}
		defer rows.Close()

		var userConfigs []UserConfig
		for rows.Next() {
			var userConfig UserConfig
			if err := rows.Scan(&userConfig.ID, &userConfig.Username, &userConfig.URL, &userConfig.Port, &userConfig.Password); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
				return
			}
			userConfigs = append(userConfigs, userConfig)
		}

		c.JSON(http.StatusOK, userConfigs)
	})

	// 获取单个用户配置
	router.GET("/user-configs/:id", func(c *gin.Context) {
		id := c.Param("id")

		row := db.QueryRow(`SELECT * FROM user_configs WHERE id = \$1`, id)

		var userConfig UserConfig
		if err := row.Scan(&userConfig.ID, &userConfig.Username, &userConfig.URL, &userConfig.Port, &userConfig.Password); err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": "user config not found"})
			return
		}

		c.JSON(http.StatusOK, userConfig)
	})

	// 创建用户配置
	router.POST("/user-configs", func(c *gin.Context) {
		var userConfig UserConfig

		if err := c.ShouldBindJSON(&userConfig); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		result, err := db.Exec(`INSERT INTO user_configs (username, url, port, password) VALUES (\$1, \$2, \$3, \$4) RETURNING id`, userConfig.Username, userConfig.URL, userConfig.Port, userConfig.Password)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		id, err := result.LastInsertId()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		userConfig.ID = int(id)

		c.JSON(http.StatusCreated, userConfig)
	})

	// 更新用户配置
	router.PUT("/user-configs/:id", func(c *gin.Context) {
		id := c.Param("id")

		var userConfig UserConfig

		if err := c.ShouldBindJSON(&userConfig); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		result, err := db.Exec(`UPDATE user_configs SET username = \$1, url = \$2, port = \$3, password = \$4 WHERE id = \$5`, userConfig.Username, userConfig.URL, userConfig.Port, userConfig.Password, id)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		rowsAffected, err := result.RowsAffected()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		if rowsAffected == 0 {
			c.JSON(http.StatusNotFound, gin.H{"error": "user config not found"})
			return
		}

		c.JSON(http.StatusOK, userConfig)
	})

	// 删除用户配置
	router.DELETE("/user-configs/:id", func(c *gin.Context) {
		id := c.Param("id")

		result, err := db.Exec(`DELETE FROM user_configs WHERE id = \$1`, id)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		rowsAffected, err := result.RowsAffected()
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
			return
		}

		if rowsAffected == 0 {
			c.JSON(http.StatusNotFound, gin.H{"error": "user config not found"})
			return
		}

		c.JSON(http.StatusOK, gin.H{"message": "user config deleted successfully"})
	})

	// 启动 Gin 服务
	if err := router.Run(":10024"); err != nil {
		log.Fatal(err)
	}
}

```

## front

### 安装node开发环境

1. 安装nvm
2. 使用nvm安装node

```shell
nvm ls-remote
nvm install v16.20.2
```

3. 使用nvm确定node版本

```shell
nvm use v16.20.2
```

4. 安装pnpm

```shell
npm install pnpm -g
```

5. 下载vue

```shell
pnpm install vue -g
pnpm install vue@cli -g
pnpm install create-vite-app -g
```
6.创建项目

```shell
create-vite-app oh-my-code
pnpm install
pnpm run dev
pnpm run build
```

7. 下载element-ui

```shell
pnpm i element-plus
pnpm i vuex
```
8. chatgpt 搜索基本代码

### 编写前端代码

**步骤 1：创建一个 Vue.js 项目**

```
npx vite create user-management-ui
```

**步骤 2：安装 Element Plus**

```
cd user-management-ui
npm install element-plus
```

**步骤 3：在 `main.js` 中导入 Element Plus**

```javascript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

const app = createApp({})

app.use(ElementPlus)
```

**步骤 4：创建用户配置模型**

```javascript
// src/models/userConfig.js
export default class UserConfig {
  constructor(id, username, url, port, password) {
    this.id = id
    this.username = username
    this.url = url
    this.port = port
    this.password = password
  }
}
```

**步骤 5：创建用户配置服务**

```javascript
// src/services/userConfigService.js
import axios from 'axios'

const userConfigService = {
  async getAllUserConfigs() {
    const response = await axios.get('/user-configs')
    return response.data
  },
  async getUserConfigById(id) {
    const response = await axios.get(`/user-configs/${id}`)
    return response.data
  },
  async createUserConfig(userConfig) {
    const response = await axios.post('/user-configs', userConfig)
    return response.data
  },
  async updateUserConfig(userConfig) {
    const response = await axios.put(`/user-configs/${userConfig.id}`, userConfig)
    return response.data
  },
  async deleteUserConfig(id) {
    await axios.delete(`/user-configs/${id}`)
  },
}

export default userConfigService
```

**步骤 6：创建用户管理界面组件**

```javascript
// src/components/UserManagement.vue
<template>
  <div>
    <h1>用户管理</h1>
    <el-table :data="userConfigs" style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="url" label="URL" />
      <el-table-column prop="port" label="端口" width="100" />
      <el-table-column prop="password" label="密码" />
      <el-table-column
        fixed="right"
        label="操作"
        width="150"
      >
        <template #default="scope">
          <el-button
            type="text"
            @click="editUserConfig(scope.row)"
          >
            编辑
          </el-button>
          <el-button
            type="text"
            @click="deleteUserConfig(scope.row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      :title="'编辑用户配置'"
      :visible="dialogVisible"
      @close="dialogVisible = false"
    >
      <el-form :model="userConfig" label-width="120px">
        <el-form-item label="用户名">
          <el-input v-model="userConfig.username" />
        </el-form-item>
        <el-form-item label="URL">
          <el-input v-model="userConfig.url" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="userConfig.port" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="userConfig.password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUserConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref } from 'vue'
import userConfigService from '@/services/userConfigService'

export default {
  setup() {
    const userConfigs = ref([])
    const dialogVisible = ref(false)
    const userConfig = ref({
      id: '',
      username: '',
      url: '',
      port: '',
      password: '',
    })

    const getUserConfigs = async () => {
      const response = await userConfigService.getAllUserConfigs()
      userConfigs.value = response
    }

    const saveUserConfig = async () => {
      if (userConfig.value.id) {
        await userConfigService.updateUserConfig(userConfig.value)
      } else {
        await userConfigService.createUserConfig(userConfig.value)
      }
      dialogVisible.value = false
      getUserConfigs()
    }

    const deleteUserConfig = async (userConfig) => {
      await userConfigService.deleteUserConfig(userConfig.id)
      getUserConfigs()
    }

    const editUserConfig = (userConfig) => {
      userConfig.value = Object.assign({}, userConfig)
      dialogVisible.value = true
    }

    getUserConfigs()

    return {
      userConfigs,
      dialogVisible,
      userConfig,
      saveUserConfig,
      deleteUserConfig,
      editUserConfig,
    }
  },
}
</script>
```

**步骤 7：在 `App.vue` 中使用用户管理界面组件**

```javascript
<template>
  <div>
    <user-management />
  </div>
</template>

<script>
import UserManagement from './components/UserManagement.vue'

export default {
  components: {
    UserManagement,
  },
}
</script>
```

**步骤 8：运行项目**

```
npm run dev
```

现在，你就可以在浏览器中访问 `http://localhost:3000` 来查看用户管理界面了。你可以在界面上查看、修改、创建和删除用户配置。

**注意：**

* 在上面的代码中，我使用了 `axios` 来发送 HTTP 请求。你也可以使用其他的 HTTP 请求库，比如 `fetch`。
* 在上面的代码中，我使用了 `Element Plus` 作为 UI 库。你也可以使用其他的 UI 库，比如 `Ant Design Vue`。