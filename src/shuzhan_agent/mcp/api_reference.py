"""
数栈平台 API 参考文档

本模块提供数栈平台API的完整参考，供LLM在规划时自主选择合适的API端点。

服务前缀说明：
- /api/streamapp/service/ - 流计算服务（实时计算）
- /api/rdos/batch/ - 批数据服务
- /api/rdos/common/ - 通用项目接口
- /api/da/service/ - 数据开发服务
- /api/publicService/ - 公共服务

环境与URL映射（LLM需要根据环境选择）：
- 62环境: http://shuzhan62-online-test.k8s.dtstack.cn
- 63环境: http://shuzhan63-zdxx.k8s.dtstack.cn
- 生产环境: https://shuzhan-prod.k8s.dtstack.cn
"""

# ============================================================
from typing import Dict

# 项目管理接口
# ============================================================

PROJECT_APIS = {
    # 创建项目
    "create_Project": {
      "url": "/api/rdos/common/project/createProject",  # API 路径
      "description": "创建项目",
      "json": {
          "projectName": "test_0414_1",
          "projectAlias": "test_0414_1",
          "projectEngineList": [{"createModel": 0, "engineType": 1}],
          "isAllowDownload": 1,
          "scheduleStatus": 0,
          "projectOwnerId": "1"
      },
      "cookies": '',
      "headers": {
          "Content-Type": "application/json",
          "Accept": "application/json"
      }
    },

    # 查询项目
    "query_Project": {
        "method": "POST",
        "url": "api/rdos/common/project/getProjectList",
        "description": "依据项目名称查询项目",
        "params": {
            "fuzzyName": "test_0407_2",
            "page": 1,
            "pageSize": 15
        }
    },

    # 删除项目
    "delete_Project": {
        "method": "POST",
        "url": "/api/rdos/common/project/deleteProject",
        "description": "删除项目",
        "params": {
            "projectAlias": "test_0407_2",
            "projectId": 339
        }
    },

    # 项目成员
    "getProjectUsers": {
        "method": "GET",
        "url": "/api/streamapp/service/project/getProjectUsers",
        "description": "获取项目成员列表",
        "params": {
            "projectId": "项目ID"
        }
    },
    "getUicUsersNotInProject": {
        "method": "GET",
        "url": "/api/streamapp/service/project/getUicUsersNotInProject",
        "description": "获取可添加到项目的用户列表",
        "params": {
            "projectId": "项目ID"
        }
    }
}

# ============================================================
# 任务管理接口
# ============================================================

TASK_APIS = {
    # 创建/保存任务
    "saveTask": {
        "method": "POST",
        "url": "/api/streamapp/service/streamTask/addOrUpdateTask",
        "description": "创建或更新流计算任务",
        "params": {
            "projectId": "项目ID",
            "name": "任务名称",
            "taskType": "任务类型(如flink)"
        }
    },
    "saveTask_batch": {
        "method": "POST",
        "url": "/api/rdos/batch/batchTask/addOrUpdateTask",
        "description": "创建或更新批数据任务",
        "params": {
            "projectId": "项目ID",
            "name": "任务名称",
            "taskType": "任务类型"
        }
    },

    # 查询任务
    "getTaskList": {
        "method": "GET",
        "url": "/api/streamapp/service/streamTask/getTaskList",
        "description": "查询流计算任务列表",
        "params": {
            "projectId": "项目ID",
            "pageNum": "页码",
            "pageSize": "每页数量"
        }
    },
    "getTaskById": {
        "method": "GET",
        "url": "/api/streamapp/service/streamTask/getTaskById",
        "description": "根据ID获取任务详情",
        "params": {
            "taskId": "任务ID"
        }
    },
    "getTaskById_batch": {
        "method": "GET",
        "url": "/api/rdos/batch/batchTask/getTaskById",
        "description": "根据ID获取批数据任务详情",
        "params": {
            "taskId": "任务ID"
        }
    },

    # 删除任务
    "deleteTask": {
        "method": "POST",
        "url": "/api/streamapp/service/streamTask/deleteTask",
        "description": "删除流计算任务",
        "params": {
            "taskId": "任务ID"
        }
    },
    "deleteTask_batch": {
        "method": "POST",
        "url": "/api/rdos/batch/batchTask/deleteTask",
        "description": "删除批数据任务",
        "params": {
            "taskId": "任务ID"
        }
    },

    # 启动/停止任务
    "startTask": {
        "method": "POST",
        "url": "/api/streamapp/service/streamTask/startTask",
        "description": "启动流计算任务",
        "params": {
            "taskId": "任务ID"
        }
    },
    "stopTask": {
        "method": "POST",
        "url": "/api/streamapp/service/streamTask/stopTask",
        "description": "停止流计算任务",
        "params": {
            "taskId": "任务ID"
        }
    },
    "startTask_batch": {
        "method": "POST",
        "url": "/api/rdos/batch/batchJob/startSqlImmediately",
        "description": "立即启动批数据SQL任务",
        "params": {
            "taskId": "任务ID"
        }
    },

    # 提交/发布任务
    "publishTask": {
        "method": "POST",
        "url": "/api/streamapp/service/streamTask/publishStreamTask",
        "description": "发布流计算任务",
        "params": {
            "taskId": "任务ID"
        }
    },
    "publishTask_batch": {
        "method": "POST",
        "url": "/api/rdos/batch/batchTask/publishTask",
        "description": "发布批数据任务",
        "params": {
            "taskId": "任务ID"
        }
    }
}

# ============================================================
# 数据源管理接口
# ============================================================

DATASOURCE_APIS = {
    # 数据源列表
    "getSourceList": {
        "method": "GET",
        "url": "/api/streamapp/service/streamDataSource/getSourceList",
        "description": "获取流计算数据源列表",
        "params": {
            "projectId": "项目ID(可选)"
        }
    },
    "listDataSource": {
        "method": "GET",
        "url": "/api/rdos/batch/batchDataSource/list",
        "description": "获取批数据数据源列表",
        "params": {
            "pageNum": "页码",
            "pageSize": "每页数量"
        }
    },
    "dataSourcePage": {
        "method": "GET",
        "url": "/api/publicService/dataSource/page",
        "description": "分页查询数据源",
        "params": {
            "pageNum": "页码",
            "pageSize": "每页数量",
            "name": "数据源名称(可选)"
        }
    },

    # 添加数据源
    "addSource": {
        "method": "POST",
        "url": "/api/streamapp/service/streamDataSource/addSource",
        "description": "添加流计算数据源",
        "params": {
            "projectId": "项目ID",
            "sourceName": "数据源名称",
            "sourceType": "数据源类型(mysql/oracle等)"
        }
    },
    "addDataSource": {
        "method": "POST",
        "url": "/api/publicService/addDs/addOrUpdateSource",
        "description": "添加或更新数据源(通用)",
        "params": {
            "name": "数据源名称",
            "type": "数据源类型",
            "info": {
                "url": "连接URL",
                "username": "用户名",
                "password": "密码"
            }
        }
    },

    # 删除数据源
    "deleteSource": {
        "method": "POST",
        "url": "/api/streamapp/service/streamDataSource/deleteSource",
        "description": "删除流计算数据源",
        "params": {
            "sourceId": "数据源ID"
        }
    },
    "deleteDataSource": {
        "method": "POST",
        "url": "/api/publicService/dataSource/delete",
        "description": "删除数据源(通用)",
        "params": {
            "id": "数据源ID"
        }
    },

    # 数据源详情
    "getDataSourceDetail": {
        "method": "GET",
        "url": "/api/publicService/dataSource/detail",
        "description": "获取数据源详细信息",
        "params": {
            "id": "数据源ID"
        }
    },
    "checkConnection": {
        "method": "POST",
        "url": "/api/streamapp/service/streamDataSource/checkConnection",
        "description": "测试数据源连接",
        "params": {
            "sourceId": "数据源ID"
        }
    },

    # 表管理
    "getTableList": {
        "method": "GET",
        "url": "/api/streamapp/service/streamDataSource/tablelist",
        "description": "获取数据源下的表列表",
        "params": {
            "datasourceId": "数据源ID",
            "schema": "schema名称"
        }
    },
    "getTableColumn": {
        "method": "GET",
        "url": "/api/streamapp/service/streamDataSource/tablecolumn",
        "description": "获取表字段列表",
        "params": {
            "datasourceId": "数据源ID",
            "tableName": "表名"
        }
    },
    "batchTableList": {
        "method": "GET",
        "url": "/api/rdos/batch/batchDataSource/tablelist",
        "description": "获取批数据数据源表列表",
        "params": {
            "datasourceId": "数据源ID",
            "schema": "schema名称"
        }
    },
    "batchGetColumns": {
        "method": "GET",
        "url": "/api/rdos/batch/batchDataSource/columnForSyncopate",
        "description": "获取批数据表字段",
        "params": {
            "datasourceId": "数据源ID",
            "tableName": "表名"
        }
    }
}

# ============================================================
# 目录管理接口
# ============================================================

CATALOGUE_APIS = {
    "getCatalogue": {
        "method": "GET",
        "url": "/api/streamapp/service/streamCatalogue/getCatalogue",
        "description": "获取目录列表",
        "params": {
            "projectId": "项目ID"
        }
    },
    "addCatalogue": {
        "method": "POST",
        "url": "/api/streamapp/service/streamCatalogue/addCatalogue",
        "description": "创建目录",
        "params": {
            "projectId": "项目ID",
            "name": "目录名称",
            "parentId": "父目录ID(可选)"
        }
    },
    "deleteCatalogue": {
        "method": "POST",
        "url": "/api/streamapp/service/streamCatalogue/deleteCatalogue",
        "description": "删除目录",
        "params": {
            "catalogueId": "目录ID"
        }
    },
    "updateCatalogue": {
        "method": "POST",
        "url": "/api/streamapp/service/streamCatalogue/updateCatalogue",
        "description": "更新目录",
        "params": {
            "catalogueId": "目录ID",
            "name": "新目录名称"
        }
    }
}

# ============================================================
# 告警管理接口
# ============================================================

ALARM_APIS = {
    "getAlarmList": {
        "method": "GET",
        "url": "/api/streamapp/service/streamAlarm/getAlarmList",
        "description": "获取告警规则列表",
        "params": {
            "projectId": "项目ID"
        }
    },
    "createAlarm": {
        "method": "POST",
        "url": "/api/streamapp/service/streamAlarm/createAlarm",
        "description": "创建告警规则",
        "params": {
            "projectId": "项目ID",
            "alarmName": "告警名称",
            "alarmType": "告警类型"
        }
    },
    "deleteAlarm": {
        "method": "POST",
        "url": "/api/streamapp/service/streamAlarm/deleteAlarm",
        "description": "删除告警规则",
        "params": {
            "alarmId": "告警ID"
        }
    },
    "startAlarm": {
        "method": "POST",
        "url": "/api/streamapp/service/streamAlarm/startAlarm",
        "description": "开启告警规则",
        "params": {
            "alarmId": "告警ID"
        }
    },
    "closeAlarm": {
        "method": "POST",
        "url": "/api/streamapp/service/streamAlarm/closeAlarm",
        "description": "关闭告警规则",
        "params": {
            "alarmId": "告警ID"
        }
    }
}

# ============================================================
# 函数管理接口
# ============================================================

FUNCTION_APIS = {
    "getAllFunctionName": {
        "method": "GET",
        "url": "/api/streamapp/service/streamFunction/getAllFunctionName",
        "description": "获取所有自定义函数",
        "params": {
            "projectId": "项目ID"
        }
    },
    "addFunction": {
        "method": "POST",
        "url": "/api/streamapp/service/streamFunction/addFunction",
        "description": "添加自定义函数",
        "params": {
            "projectId": "项目ID",
            "functionName": "函数名称",
            "functionType": "函数类型"
        }
    },
    "deleteFunction": {
        "method": "POST",
        "url": "/api/streamapp/service/streamFunction/deleteFunction",
        "description": "删除自定义函数",
        "params": {
            "functionId": "函数ID"
        }
    }
}

# ============================================================
# 资源管理接口
# ============================================================

RESOURCE_APIS = {
    "getResources": {
        "method": "GET",
        "url": "/api/streamapp/service/streamResource/getResources",
        "description": "获取项目资源列表",
        "params": {
            "projectId": "项目ID"
        }
    },
    "addResource": {
        "method": "POST",
        "url": "/api/streamapp/upload/streamResource/addResource",
        "description": "上传资源文件",
        "params": {
            "projectId": "项目ID",
            "resourceName": "资源名称"
        }
    },
    "deleteResource": {
        "method": "POST",
        "url": "/api/streamapp/service/streamResource/deleteResource",
        "description": "删除资源",
        "params": {
            "resourceId": "资源ID"
        }
    }
}


# ============================================================
# 辅助函数
# ============================================================

def get_all_apis() -> dict:
    """获取所有API的合并字典"""
    all_apis = {}
    all_apis.update(PROJECT_APIS)
    # all_apis.update(TASK_APIS)
    # all_apis.update(DATASOURCE_APIS)
    # all_apis.update(CATALOGUE_APIS)
    # all_apis.update(ALARM_APIS)
    # all_apis.update(FUNCTION_APIS)
    # all_apis.update(RESOURCE_APIS)
    return all_apis


def format_api_for_llm() -> Dict[str, str]:
    """格式化API列表供LLM参考（返回name->description字典）"""
    apis = get_all_apis()
    return {name: arguments for name, arguments in apis.items()}


if __name__ == "__main__":
    print(format_api_for_llm()['create_Project'])
