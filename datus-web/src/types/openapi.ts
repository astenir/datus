

export interface paths {
    "/api/v1/chat/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["stream_chat_api_v1_chat_stream_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["stream_chat_feedback_api_v1_chat_feedback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["resume_chat_api_v1_chat_resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["stop_chat_api_v1_chat_stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/sessions/{session_id}/compact": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["compact_chat_session_api_v1_chat_sessions__session_id__compact_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_sessions_api_v1_chat_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;

        delete: operations["delete_session_api_v1_chat_sessions__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_chat_history_api_v1_chat_history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/user_interaction": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["submit_user_interaction_api_v1_chat_user_interaction_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/insert": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["insert_message_api_v1_chat_insert_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat/tool_result": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["submit_tool_result_api_v1_chat_tool_result_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sql/execute": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["execute_sql_api_v1_sql_execute_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sql/stop_execute": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["stop_execute_sql_api_v1_sql_stop_execute_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/context/{context_type}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["execute_context_api_v1_context__context_type__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/internal/{command}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["execute_internal_command_api_v1_internal__command__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/catalog/list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_catalogs_api_v1_catalog_list_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/table/detail": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_table_detail_api_v1_table_detail_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/semantic_model": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_semantic_model_api_v1_semantic_model_get"];
        put?: never;

        post: operations["save_semantic_model_api_v1_semantic_model_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/semantic_model/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["validate_semantic_model_api_v1_semantic_model_validate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_subject_tree_api_v1_subject_tree_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_directory_api_v1_subject_tree_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/rename": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["rename_subject_api_v1_subject_tree_rename_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/delete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;

        delete: operations["delete_subject_api_v1_subject_tree_delete_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/metric": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["get_metric_api_v1_subject_tree_metric_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/metric/dimensions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["get_metric_dimensions_api_v1_subject_tree_metric_dimensions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/metric/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["preview_metric_api_v1_subject_tree_metric_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/metric/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_metric_api_v1_subject_tree_metric_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/metric/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["edit_metric_api_v1_subject_tree_metric_edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/reference_sql": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["get_reference_sql_api_v1_subject_tree_reference_sql_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/reference_sql/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_reference_sql_api_v1_subject_tree_reference_sql_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/reference_sql/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["edit_reference_sql_api_v1_subject_tree_reference_sql_edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject-tree/semantic_model/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["edit_semantic_model_api_v1_subject_tree_semantic_model_edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_subject_list_api_v1_subject_list_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_directory_api_v1_subject_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/rename": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["rename_subject_api_v1_subject_rename_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/delete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;

        delete: operations["delete_subject_api_v1_subject_delete_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/metric": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["get_metric_api_v1_subject_metric_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/metric/dimensions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["get_metric_dimensions_api_v1_subject_metric_dimensions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/metric/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["preview_metric_api_v1_subject_metric_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/reference_sql": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["get_reference_sql_api_v1_subject_reference_sql_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/reference_sql/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_reference_sql_api_v1_subject_reference_sql_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/reference_sql/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["edit_reference_sql_api_v1_subject_reference_sql_edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/metric/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_metric_api_v1_subject_metric_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/metric/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["edit_metric_api_v1_subject_metric_edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/subject/semantic_model/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["edit_semantic_model_api_v1_subject_semantic_model_edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/config/agent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_agent_config_endpoint_api_v1_config_agent_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/config/datasources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;

        put: operations["update_datasources_endpoint_api_v1_config_datasources_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/config/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;

        put: operations["update_models_endpoint_api_v1_config_models_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/config/models/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["probe_model_connectivity_endpoint_api_v1_config_models_test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/config/datasources/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["probe_datasource_connectivity_endpoint_api_v1_config_datasources_test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_models_api_v1_models_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/mcp/servers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_servers_api_v1_mcp_servers_get"];
        put?: never;

        post: operations["add_server_api_v1_mcp_servers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/mcp/servers/{server_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;

        delete: operations["remove_server_api_v1_mcp_servers__server_name__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/mcp/servers/{server_name}/connectivity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["check_connectivity_api_v1_mcp_servers__server_name__connectivity_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/mcp/servers/{server_name}/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_tools_api_v1_mcp_servers__server_name__tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/mcp/servers/{server_name}/tools/{tool_name}/call": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["call_tool_api_v1_mcp_servers__server_name__tools__tool_name__call_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/mcp/servers/{server_name}/filters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_tool_filter_api_v1_mcp_servers__server_name__filters_get"];

        put: operations["set_tool_filter_api_v1_mcp_servers__server_name__filters_put"];
        post?: never;

        delete: operations["remove_tool_filter_api_v1_mcp_servers__server_name__filters_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kb/uploads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_kb_upload_api_v1_kb_uploads_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kb/uploads/{upload_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_kb_upload_api_v1_kb_uploads__upload_id__get"];
        put?: never;
        post?: never;

        delete: operations["delete_kb_upload_api_v1_kb_uploads__upload_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kb/bootstrap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["bootstrap_kb_api_v1_kb_bootstrap_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kb/bootstrap/{stream_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["cancel_bootstrap_api_v1_kb_bootstrap__stream_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kb/bootstrap-docs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["bootstrap_docs_api_v1_kb_bootstrap_docs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kb/bootstrap-docs/{stream_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["cancel_doc_bootstrap_api_v1_kb_bootstrap_docs__stream_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agent/use_tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_agent_use_tools_api_v1_agent_use_tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_agent_api_v1_agent_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agent/list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_agents_api_v1_agent_list_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agent/create": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["create_agent_api_v1_agent_create_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agent/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["edit_agent_api_v1_agent_edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agent/delete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;

        delete: operations["delete_agent_api_v1_agent_delete_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agent/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_available_tools_api_v1_agent_tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/data_visualization": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["data_visualization_api_v1_data_visualization_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tools/{tool_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["execute_tool_api_v1_tools__tool_name__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/success-stories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["save_success_story_api_v1_success_stories_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/detail": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_dashboard_detail_api_v1_dashboard_detail_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/query": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["run_dashboard_query_api_v1_dashboard_query_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/report/detail": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_report_detail_api_v1_report_detail_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_me_api_v1_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/permissions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_my_permissions_api_v1_me_permissions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/datasource-grants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_my_datasource_grants_api_v1_me_datasource_grants_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/features": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_my_features_api_v1_me_features_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_my_sessions_api_v1_me_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_my_usage_api_v1_me_usage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboards": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_dashboards_api_v1_dashboards_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboards/{slug}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_dashboard_detail_api_v1_dashboards__slug__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboards/{slug}/acl": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_dashboard_share_acl_api_v1_dashboards__slug__acl_get"];

        put: operations["put_dashboard_share_acl_api_v1_dashboards__slug__acl_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboards/{slug}/html": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_dashboard_html_by_path_api_v1_dashboards__slug__html_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_reports_api_v1_reports_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/{slug}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_report_detail_api_v1_reports__slug__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/{slug}/acl": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_report_share_acl_api_v1_reports__slug__acl_get"];

        put: operations["put_report_share_acl_api_v1_reports__slug__acl_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/reports/{slug}/html": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_report_html_by_path_api_v1_reports__slug__html_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/artifacts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_artifacts_api_v1_admin_artifacts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/artifacts/{artifact_type}/{slug}/acl": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_artifact_acl_api_v1_admin_artifacts__artifact_type___slug__acl_get"];

        put: operations["put_admin_artifact_acl_api_v1_admin_artifacts__artifact_type___slug__acl_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_available_agents_api_v1_agents_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agents/{agent_id}/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_available_agent_tools_api_v1_agents__agent_id__tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/agents/{agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_available_agent_api_v1_agents__agent_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/agents/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_agent_tools_api_v1_admin_agents_tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/agents/tool-reference": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_agent_tool_reference_api_v1_admin_agents_tool_reference_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_agents_api_v1_admin_agents_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/agents/{agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_agent_api_v1_admin_agents__agent_id__get"];

        put: operations["upsert_admin_agent_api_v1_admin_agents__agent_id__put"];
        post?: never;

        delete: operations["delete_admin_agent_api_v1_admin_agents__agent_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/agents/{agent_id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;

        put: operations["set_admin_agent_status_api_v1_admin_agents__agent_id__status_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/agents/{agent_id}/acl": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_agent_acl_api_v1_admin_agents__agent_id__acl_get"];

        put: operations["set_admin_agent_acl_api_v1_admin_agents__agent_id__acl_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/datasources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_datasources_endpoint_api_v1_admin_datasources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/datasource-grants": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_datasource_grants_api_v1_admin_datasource_grants_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_datasource_grant_api_v1_admin_datasource_grants__subject_type___subject_id___datasource_key__get"];

        put: operations["upsert_admin_datasource_grant_api_v1_admin_datasource_grants__subject_type___subject_id___datasource_key__put"];
        post?: never;

        delete: operations["delete_admin_datasource_grant_api_v1_admin_datasource_grants__subject_type___subject_id___datasource_key__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/datasource-default": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;

        put: operations["set_project_default_datasource_endpoint_api_v1_admin_datasource_default_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/audit-logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_audit_logs_api_v1_admin_audit_logs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/audit-logs/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["export_audit_logs_api_v1_admin_audit_logs_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_sessions_api_v1_admin_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_session_api_v1_admin_sessions__session_id__get"];
        put?: never;
        post?: never;

        delete: operations["delete_admin_session_api_v1_admin_sessions__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/sessions/{session_id}/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["stop_admin_session_api_v1_admin_sessions__session_id__stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_users_api_v1_admin_users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_user_api_v1_admin_users__user_id__get"];

        put: operations["upsert_admin_user_api_v1_admin_users__user_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}/disable": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["disable_admin_user_api_v1_admin_users__user_id__disable_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}/enable": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["enable_admin_user_api_v1_admin_users__user_id__enable_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_roles_api_v1_admin_roles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/roles/{role_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_role_api_v1_admin_roles__role_id__get"];

        put: operations["upsert_admin_role_api_v1_admin_roles__role_id__put"];
        post?: never;

        delete: operations["delete_admin_role_api_v1_admin_roles__role_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/roles/{role_id}/permissions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;

        put: operations["set_admin_role_permissions_api_v1_admin_roles__role_id__permissions_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/users/{user_id}/roles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_user_roles_api_v1_admin_users__user_id__roles_get"];

        put: operations["set_admin_user_roles_api_v1_admin_users__user_id__roles_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/quotas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_quotas_api_v1_admin_quotas_get"];

        put: operations["upsert_admin_quota_api_v1_admin_quotas_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_usage_api_v1_admin_usage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/secrets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["list_admin_secrets_api_v1_admin_secrets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/admin/secrets/{name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_admin_secret_api_v1_admin_secrets__name__get"];

        put: operations["upsert_admin_secret_api_v1_admin_secrets__name__put"];
        post?: never;

        delete: operations["delete_admin_secret_api_v1_admin_secrets__name__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/system/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["get_system_status_api_v1_system_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["root__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };

        get: operations["health_check_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/token": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["authenticate_auth_token_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workflows/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["run_workflow_workflows_run_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/workflows/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;

        post: operations["record_feedback_workflows_feedback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {

        AddServerInput: {

            name: string;

            type: string;

            command?: string | null;

            args?: string[] | null;

            url?: string | null;

            headers?: {
                [key: string]: string;
            } | null;

            timeout?: number | null;

            env?: {
                [key: string]: string;
            } | null;

            cwd?: string | null;
        };

        AdminArtifactSummary: {

            artifact_type: "report" | "dashboard";
            manifest: components["schemas"]["ArtifactManifest"];
        };

        AdminDatasourceGrantSummary: {

            subject_type: string;

            subject_id: string;

            datasource_key: string;

            effect: string;

            scope?: {
                [key: string]: unknown;
            };

            created_at?: string | null;

            updated_at?: string | null;
        };

        AdminDatasourceSummary: {

            name: string;

            type?: string | null;

            is_default: boolean;
        };

        AdminQuotaSummary: {

            subject_type: string;

            subject_id: string;

            resource: string;

            limit: number;

            window_seconds: number;

            enabled: boolean;

            created_at?: string | null;

            updated_at?: string | null;
        };

        AdminRoleSummary: {

            role_id: string;

            name: string;

            description?: string | null;

            permissions?: string[];

            built_in: boolean;

            created_at?: string | null;

            updated_at?: string | null;
        };

        AdminSecretSummary: {

            name: string;

            provider: string;

            ref_hint: string;

            description?: string | null;

            enabled: boolean;

            created_at?: string | null;

            updated_at?: string | null;
        };

        AdminSessionDetail: {

            session_id: string;

            owner_user_id?: string | null;

            status: string;

            is_running: boolean;

            created_at?: string | null;

            updated_at?: string | null;

            event_count: number;

            exists_on_disk?: boolean | null;

            consumer_offset: number;

            error?: string | null;
        };

        AdminSessionSummary: {

            session_id: string;

            owner_user_id?: string | null;

            status: string;

            is_running: boolean;

            created_at?: string | null;

            updated_at?: string | null;

            event_count: number;

            exists_on_disk?: boolean | null;
        };

        AdminUsageSummary: {

            subject_type: string;

            subject_id: string;

            resource: string;

            used: number;

            window_start?: string | null;

            window_seconds?: number | null;

            updated_at?: string | null;
        };

        AdminUserDatasourceGrantSummary: {

            subject_type: string;

            subject_id: string;

            datasource_key: string;

            effect: string;

            scope?: {
                [key: string]: unknown;
            };

            created_at?: string | null;

            updated_at?: string | null;
        };

        AdminUserDetail: {

            user_id: string;

            display_name?: string | null;

            email?: string | null;

            enabled: boolean;

            external_user_id?: string | null;

            department?: string | null;

            title?: string | null;

            last_seen_at?: string | null;

            role_ids?: string[];

            role_count: number;

            direct_datasource_grant_count: number;

            created_at?: string | null;

            updated_at?: string | null;

            roles?: components["schemas"]["AdminUserRoleSummary"][];

            effective_permissions?: string[];

            direct_datasource_grants?: components["schemas"]["AdminUserDatasourceGrantSummary"][];

            role_datasource_grants?: components["schemas"]["AdminUserDatasourceGrantSummary"][];

            role_datasource_grant_count: number;

            effective_datasource_grant_count: number;
        };

        AdminUserRoleSummary: {

            role_id: string;

            name?: string | null;

            permissions?: string[];

            built_in: boolean;
        };

        AdminUserRolesSummary: {

            user_id: string;

            role_ids?: string[];
        };

        AdminUserSummary: {

            user_id: string;

            display_name?: string | null;

            email?: string | null;

            enabled: boolean;

            external_user_id?: string | null;

            department?: string | null;

            title?: string | null;

            last_seen_at?: string | null;

            role_ids?: string[];

            role_count: number;

            direct_datasource_grant_count: number;

            created_at?: string | null;

            updated_at?: string | null;
        };

        AgentAcl: {

            visibility: string;

            allowed_roles?: string[];

            allowed_user_ids?: string[];
        };

        AgentConfigSummaryData: {

            target?: unknown | null;

            models?: {
                [key: string]: unknown;
            };

            current_datasource?: string | null;

            datasources?: {
                [key: string]: unknown;
            };

            home: string;
        };

        AgentListData: {

            agents?: components["schemas"]["AgentSummary"][];
        };

        AgentMutationData: {

            id: string;

            name: string;
        };

        AgentSummary: {

            id: string;

            name: string;

            type: string;

            description: string;
        };

        AgentToolsData: {

            tools?: {
                [key: string]: string[];
            };
        };

        AgentUseToolsData: {

            default_tools?: string[];

            tool_types?: {
                [key: string]: components["schemas"]["ToolCategoryData"];
            };
        };

        ArtifactAcl: {

            owner_user_id: string;

            visibility: "private" | "role" | "enterprise";

            allowed_roles?: string[];

            allowed_user_ids?: string[];

            datasources?: string[];
        };

        ArtifactFile: {

            path: string;

            content: string;
        };

        ArtifactManifest: {

            slug: string;

            name: string;

            description: string;

            kind: "report" | "dashboard";

            created_at: string;

            updated_at?: string | null;

            datasources?: string[];

            key_tables?: string[];
        };

        ArtifactShare: {

            owner_user_id: string;

            visibility: "private" | "role" | "enterprise";

            allowed_roles?: string[];

            allowed_user_ids?: string[];
        };

        ArtifactShareUpdate: {

            visibility: "private" | "role" | "enterprise";

            allowed_roles?: string[];

            allowed_user_ids?: string[];
        };

        AuditLogEntry: {

            user_id?: string | null;

            action: string;

            resource_type: string;

            resource_id?: string | null;

            decision: string;

            reason?: string | null;

            request_id?: string | null;

            metadata?: {
                [key: string]: unknown;
            };
        };

        Body_create_kb_upload_api_v1_kb_uploads_post: {

            purpose: components["schemas"]["KbUploadPurpose"];

            files: string[];

            platform?: string | null;

            datasource_id?: string | null;

            description?: string | null;
        };

        BootstrapDocInput: {

            platform: string;

            build_mode: "overwrite" | "check";

            pool_size: number;

            source_type?: string | null;

            source?: string | null;

            upload_id?: string | null;

            version?: string | null;

            github_ref?: string | null;

            github_token?: string | null;

            paths?: string[] | null;

            chunk_size?: number | null;

            max_depth?: number | null;

            include_patterns?: string[] | null;

            exclude_patterns?: string[] | null;
        };

        BootstrapKbInput: {

            components: components["schemas"]["KbComponent"][];

            strategy: "overwrite" | "check" | "incremental";

            schema_linking_type: string;

            catalog: string;

            database_name: string;

            success_story?: string | null;

            upload_id?: string | null;

            success_story_upload_id?: string | null;

            success_story_file_id?: string | null;

            subject_tree?: string[] | null;

            sql_dir?: string | null;

            reference_sql_upload_id?: string | null;
        };

        CallToolInput: {

            parameters?: {
                [key: string]: unknown;
            };
        };

        ChannelBinding: {

            channels?: components["schemas"]["ChannelInput"][] | null;
        };

        ChannelInput: {

            enabled: boolean;

            type: string;

            name: string;

            secrets?: {
                [key: string]: unknown;
            };
        };

        ChartData: {

            chart_type: "Bar" | "Line" | "Pie" | "Scatter" | "Unknown";

            columns: string[];

            numeric_columns: string[];

            x_col?: string | null;

            y_cols?: string[] | null;

            reason: string;
        };

        ChatHistoryData: {

            messages?: components["schemas"]["SSEMessagePayload"][];
        };

        ChatSessionData: {

            sessions?: components["schemas"]["ChatSessionItemInfo"][];

            total_count: number;
        };

        ChatSessionItemInfo: {

            user_query?: string | null;

            session_id: string;

            created_at: string;

            last_updated: string;

            total_turns: number;

            token_count: number;

            last_sql_queries?: string[];

            is_active: boolean;
        };

        ColumnInfo: {

            name: string;

            type: string;

            nullable: boolean;

            default_value?: string | null;

            pk: boolean;
        };

        CompactSessionData: {

            session_id: string;

            success: boolean;

            new_token_count?: number | null;

            tokens_saved?: number | null;

            compression_ratio?: string | null;

            error?: string | null;
        };

        ContextResultData: {

            tables?: components["schemas"]["TableInfo"][] | null;

            total_count?: number | null;

            context_info?: {
                [key: string]: unknown;
            } | null;

            output?: unknown | null;
        };

        CreateAgentInput: {

            name: string;

            datasource_id: string;

            type: string;

            artifact_slug?: string | null;

            description?: string | null;

            prompt_template?: string | null;

            prompt_version: string | null;

            prompt_language: string;

            tools?: string[] | null;

            mcp?: string[] | null;

            skills?: string[] | null;

            catalogs?: string[] | null;

            subjects?: string[] | null;

            permissions?: {
                [key: string]: unknown;
            } | null;

            hooks?: {
                [key: string]: unknown;
            } | null;

            rules?: string[] | null;

            max_turns: number | null;

            workspace_root?: string | null;

            adapter_type?: string | null;

            sql_file_threshold?: number | null;

            sql_preview_lines?: number | null;
        };

        CreateDirectoryInput: {

            subject_path: string[];
        };

        CsvData: {

            columns: string[];

            data: {
                [key: string]: unknown;
            }[];
        };

        DashboardDetail: {

            slug: string;

            name: string;

            description: string;

            manifest: components["schemas"]["ArtifactManifest"];

            created_at?: string | null;

            files: components["schemas"]["ArtifactFile"][];

            templates?: components["schemas"]["QueryTemplateMetaFile"][];
        };

        DashboardQueryRequest: {

            dashboard_slug: string;

            query_slug: string;

            params?: {
                [key: string]: unknown;
            };

            published_version?: number | null;
        };

        DataInsight: {

            period?: string | null;

            filters?: string[] | null;

            insight?: string | null;
        };

        DataVisualizationData: {

            chart: components["schemas"]["ChartData"];

            data_insight?: components["schemas"]["DataInsight"] | null;
        };

        DataVisualizationRequest: {
            csv_data: components["schemas"]["CsvData"];

            chart_type?: ("Bar" | "Line" | "Pie" | "Scatter" | "Unknown") | null;

            sql?: string | null;

            user_question?: string | null;
        };

        DatabaseInfo: {

            name: string;

            uri: string;

            type: string;

            current: boolean;

            catalog_name?: string | null;

            schema_name?: string | null;

            connection_status: string;

            tables_count?: number | null;

            last_accessed?: string | null;

            tables?: string[] | null;
        };

        DatabasesData: {

            databases: components["schemas"]["DatabaseInfo"][];
        };

        DeleteSubjectInput: {

            type: components["schemas"]["SubjectNodeType"];

            subject_path: string[];
        };

        EditAgentInput: {

            id: string;

            name?: string | null;

            description?: string | null;

            system_prompt?: string | null;

            prompt_version?: string | null;

            prompt_language?: string | null;

            tools?: string[] | null;

            mcp?: string[] | null;

            skills?: string[] | null;

            scoped_context?: {
                [key: string]: unknown;
            } | null;

            permissions?: {
                [key: string]: unknown;
            } | null;

            catalogs?: string[] | null;

            subjects?: string[] | null;

            hooks?: {
                [key: string]: unknown;
            } | null;

            rules?: string[] | null;

            max_turns?: number | null;

            workspace_root?: string | null;

            adapter_type?: string | null;

            sql_file_threshold?: number | null;

            sql_preview_lines?: number | null;

            artifact_slug?: string | null;

            channels?: components["schemas"]["ChannelBinding"] | null;
        };

        EditMetricInput: {

            subject_path: string[];

            yaml: string;
        };

        EditSemanticModelInput: {

            entry_id: string;

            update_values: {
                [key: string]: unknown;
            };
        };

        EnterpriseAgentDetail: {

            agent_id: string;

            name: string;

            description?: string | null;

            node_class: string;

            status: string;

            source: string;

            owner_user_id?: string | null;

            datasource_id?: string | null;

            artifact_slug?: string | null;
            acl?: components["schemas"]["AgentAcl"] | null;

            created_at?: string | null;

            updated_at?: string | null;

            prompt_template?: string | null;

            prompt_language: string;

            prompt_version: string | null;

            tools?: string[];

            mcp?: string[];

            skills?: string[];

            scoped_context?: {
                [key: string]: unknown;
            };

            rules?: string[];

            max_turns: number;
        };

        EnterpriseAgentSummary: {

            agent_id: string;

            name: string;

            description?: string | null;

            node_class: string;

            status: string;

            source: string;

            owner_user_id?: string | null;

            datasource_id?: string | null;

            artifact_slug?: string | null;
            acl?: components["schemas"]["AgentAcl"] | null;

            created_at?: string | null;

            updated_at?: string | null;
        };

        ExecuteContextData: {

            context_type: string;

            database_name?: string | null;

            schema_name?: string | null;

            result: components["schemas"]["ContextResultData"];
        };

        ExecuteContextInput: {

            context_type: string;

            database_name?: string | null;

            schema_name?: string | null;

            args: string;
        };

        ExecuteSQLData: {

            execute_task_id: string;

            sql_query: string;

            row_count?: number | null;

            sql_return?: string | null;

            result_format: string;

            execution_time: number;

            executed_at: string;

            columns?: string[] | null;
        };

        ExecuteSQLInput: {

            database_name?: string | null;

            sql_query: string;

            result_format: string;

            system: boolean;

            execute_task_id?: string | null;
        };

        FeedbackChatInput: {

            message: string;

            session_id?: string | null;

            model?: string | null;

            plan_mode: boolean;

            source?: string | null;

            interactive?: boolean | null;

            datasource?: string | null;

            catalog?: string | null;

            database?: string | null;

            db_schema?: string | null;

            max_turns: number;

            workspace_root?: string | null;

            table_paths?: string[] | null;

            metric_paths?: string[] | null;

            sql_paths?: string[] | null;

            knowledge_paths?: string[] | null;

            stream_response?: boolean | null;

            context_id?: string | null;

            source_session_id: string;

            reaction_emoji: string;

            reference_msg: string;

            reaction_msg?: string | null;
        };

        FeedbackRequest: {

            task_id: string;

            status: components["schemas"]["FeedbackStatus"];
        };

        FeedbackResponse: {

            task_id: string;

            acknowledged: boolean;

            recorded_at: string;
        };

        FeedbackStatus: "success" | "failed";

        FuncToolResult: {

            success: number;

            error?: string | null;

            result?: unknown | null;
        };

        GetAgentData: {
            agent: components["schemas"]["IAgentInfo"];
        };

        GetSemanticModelData: {

            yaml: string;
        };

        GetTableDetailData: {
            table: components["schemas"]["TableDetailData"];
        };

        HTTPValidationError: {

            detail?: components["schemas"]["ValidationError"][];
        };

        HealthResponse: {

            status: string;

            version: string;

            database_status: {
                [key: string]: string;
            };

            llm_status: string;
        };

        IAgentInfo: {

            id: string;

            name: string;

            type: string;

            description: string;

            config_yaml?: string | null;

            system_prompt?: string | null;

            tools?: string[];

            catalogs?: string[];

            subjects?: string[];

            rules?: string[];

            created_at?: string | null;
        };

        IMessageContent: {

            type: string;

            payload: {
                [key: string]: unknown;
            };
        };

        IndexInfo: {

            name: string;

            columns: string[];

            type: string;
        };

        InsertMessageData: {

            session_id: string;

            queued_count: number;
        };

        InsertMessageInput: {

            session_id: string;

            message: string;
        };

        InternalCommandData: {

            command: string;

            args: string;

            result: components["schemas"]["InternalCommandResultData"];
        };

        InternalCommandInput: {

            command: string;

            args: string;
        };

        InternalCommandResultData: {

            command_output: string;

            action_taken: string;

            context_changed: boolean;

            data?: unknown | null;
        };

        KbComponent: "metadata" | "semantic_model" | "metrics" | "reference_sql";

        KbUploadDeleteResponse: {

            upload_id: string;

            deleted: boolean;
        };

        KbUploadPurpose: "success_story_csv" | "reference_sql" | "platform_docs";

        KbUploadRecord: {

            upload_id: string;
            purpose: components["schemas"]["KbUploadPurpose"];

            files: components["schemas"]["KbUploadedFile"][];

            created_at: string;

            expires_at?: string | null;

            status: components["schemas"]["KbUploadStatus"];

            owner_user_id?: string | null;

            project_id: string;

            metadata?: {
                [key: string]: string;
            };
        };

        KbUploadStatus: "available" | "deleted" | "expired";

        KbUploadedFile: {

            file_id: string;

            filename: string;

            size: number;

            content_type?: string | null;

            relative_path: string;
        };

        MeSummary: {

            user_id?: string | null;

            project_id?: string | null;

            roles?: string[];

            permissions?: string[];

            datasource_grants?: {
                [key: string]: unknown;
            };

            features?: {
                [key: string]: boolean;
            };

            is_admin: boolean;
        };

        MetricDimensionItem: {

            name: string;

            type?: string | null;

            description?: string | null;

            is_primary_key?: boolean | null;
        };

        MetricDimensionPreflight: {

            message: string;

            invalid_dimensions?: {
                [key: string]: unknown;
            }[];

            common_dimensions?: string[];

            suggested_metric_groups?: {
                [key: string]: unknown;
            }[];
        };

        MetricDimensionsData: {

            metric: string;

            dimensions?: components["schemas"]["MetricDimensionItem"][];
        };

        MetricInfo: {

            name: string;

            yaml: string;
        };

        MetricPreviewData: {

            metric: string;

            sql?: string | null;

            database?: string | null;

            preflight_error?: components["schemas"]["MetricDimensionPreflight"] | null;
        };

        MetricPreviewInput: {

            subject_path: string[];

            dimensions?: string[] | null;

            time_start?: string | null;

            time_end?: string | null;

            time_granularity?: string | null;

            where?: string | null;

            limit?: number | null;

            order_by?: string[] | null;
        };

        Mode: "sync" | "async";

        ModelInfo: {

            provider: string;

            id: string;

            model?: string | null;

            name?: string | null;

            context_length?: number | null;

            max_tokens?: number | null;

            pricing?: components["schemas"]["ModelPricing"] | null;
        };

        ModelPricing: {

            prompt?: string | null;

            completion?: string | null;
        };

        ModelsData: {

            models: components["schemas"]["ModelInfo"][];

            providers: string[];

            current_model?: string | null;

            fetched_at?: string | null;

            source: string;
        };

        MutationResultData: {

            updated: boolean;
        };

        ProbeDatasourceRequest: {

            type: string;
        } & {
            [key: string]: unknown;
        };

        ProbeModelRequest: {

            type: string;

            model: string;

            api_key?: string | null;

            base_url?: string | null;
        } & {
            [key: string]: unknown;
        };

        ProbeResultData: {

            ok: boolean;

            message?: string | null;
        };

        QueryColumnMeta: {

            name: string;

            type: "string" | "integer" | "number" | "date" | "boolean";
        };

        QueryTemplateMetaFile: {

            slug: string;

            description: string;

            datasource: string;

            params: components["schemas"]["TemplateParamDecl"][];

            columns: components["schemas"]["QueryColumnMeta"][];

            sample_params?: {
                [key: string]: unknown;
            };

            sample_row_count: number;

            saved_at: string;
        };

        ReferenceSQLInfo: {

            name: string;

            sql: string;

            summary: string;

            search_text: string;
        };

        ReferenceSQLInput: {

            name: string;

            sql: string;

            summary: string;

            search_text: string;

            subject_path: string[];
        };

        RenameSubjectInput: {

            type: components["schemas"]["SubjectNodeType"];

            subject_path: string[];

            new_subject_path: string[];
        };

        ReportDetail: {

            slug: string;

            name: string;

            description: string;

            manifest: components["schemas"]["ArtifactManifest"];

            created_at?: string | null;

            files: components["schemas"]["ArtifactFile"][];
        };

        Result_AdminDatasourceGrantSummary_: {

            success: boolean;

            data?: components["schemas"]["AdminDatasourceGrantSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AdminQuotaSummary_: {

            success: boolean;

            data?: components["schemas"]["AdminQuotaSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AdminRoleSummary_: {

            success: boolean;

            data?: components["schemas"]["AdminRoleSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AdminSecretSummary_: {

            success: boolean;

            data?: components["schemas"]["AdminSecretSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AdminSessionDetail_: {

            success: boolean;

            data?: components["schemas"]["AdminSessionDetail"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AdminUserDetail_: {

            success: boolean;

            data?: components["schemas"]["AdminUserDetail"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AdminUserRolesSummary_: {

            success: boolean;

            data?: components["schemas"]["AdminUserRolesSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AdminUserSummary_: {

            success: boolean;

            data?: components["schemas"]["AdminUserSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AgentAcl_: {

            success: boolean;

            data?: components["schemas"]["AgentAcl"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AgentConfigSummaryData_: {

            success: boolean;

            data?: components["schemas"]["AgentConfigSummaryData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AgentListData_: {

            success: boolean;

            data?: components["schemas"]["AgentListData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AgentMutationData_: {

            success: boolean;

            data?: components["schemas"]["AgentMutationData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AgentToolsData_: {

            success: boolean;

            data?: components["schemas"]["AgentToolsData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_AgentUseToolsData_: {

            success: boolean;

            data?: components["schemas"]["AgentUseToolsData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ArtifactAcl_: {

            success: boolean;

            data?: components["schemas"]["ArtifactAcl"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ArtifactShare_: {

            success: boolean;

            data?: components["schemas"]["ArtifactShare"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ChatHistoryData_: {

            success: boolean;

            data?: components["schemas"]["ChatHistoryData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ChatSessionData_: {

            success: boolean;

            data?: components["schemas"]["ChatSessionData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_CompactSessionData_: {

            success: boolean;

            data?: components["schemas"]["CompactSessionData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_DashboardDetail_: {

            success: boolean;

            data?: components["schemas"]["DashboardDetail"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_DataVisualizationData_: {

            success: boolean;

            data?: components["schemas"]["DataVisualizationData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_DatabasesData_: {

            success: boolean;

            data?: components["schemas"]["DatabasesData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_Dict_str__Any__: {

            success: boolean;

            data?: {
                [key: string]: unknown;
            } | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_EnterpriseAgentDetail_: {

            success: boolean;

            data?: components["schemas"]["EnterpriseAgentDetail"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ExecuteContextData_: {

            success: boolean;

            data?: components["schemas"]["ExecuteContextData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ExecuteSQLData_: {

            success: boolean;

            data?: components["schemas"]["ExecuteSQLData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_FuncToolResult_: {

            success: boolean;

            data?: components["schemas"]["FuncToolResult"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_GetAgentData_: {

            success: boolean;

            data?: components["schemas"]["GetAgentData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_GetSemanticModelData_: {

            success: boolean;

            data?: components["schemas"]["GetSemanticModelData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_GetTableDetailData_: {

            success: boolean;

            data?: components["schemas"]["GetTableDetailData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_InsertMessageData_: {

            success: boolean;

            data?: components["schemas"]["InsertMessageData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_InternalCommandData_: {

            success: boolean;

            data?: components["schemas"]["InternalCommandData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_List_AdminArtifactSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminArtifactSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_List_ArtifactManifest__: {

            success: boolean;

            data?: components["schemas"]["ArtifactManifest"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_MeSummary_: {

            success: boolean;

            data?: components["schemas"]["MeSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_MetricDimensionsData_: {

            success: boolean;

            data?: components["schemas"]["MetricDimensionsData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_MetricInfo_: {

            success: boolean;

            data?: components["schemas"]["MetricInfo"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_MetricPreviewData_: {

            success: boolean;

            data?: components["schemas"]["MetricPreviewData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ModelsData_: {

            success: boolean;

            data?: components["schemas"]["ModelsData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_MutationResultData_: {

            success: boolean;

            data?: components["schemas"]["MutationResultData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ProbeResultData_: {

            success: boolean;

            data?: components["schemas"]["ProbeResultData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ReferenceSQLInfo_: {

            success: boolean;

            data?: components["schemas"]["ReferenceSQLInfo"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ReportDetail_: {

            success: boolean;

            data?: components["schemas"]["ReportDetail"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_SqlQueryResultEnvelope_: {

            success: boolean;

            data?: components["schemas"]["SqlQueryResultEnvelope"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_StopExecuteSQLData_: {

            success: boolean;

            data?: components["schemas"]["StopExecuteSQLData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_SubjectListData_: {

            success: boolean;

            data?: components["schemas"]["SubjectListData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_SuccessStoryData_: {

            success: boolean;

            data?: components["schemas"]["SuccessStoryData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_SystemStatusSummary_: {

            success: boolean;

            data?: components["schemas"]["SystemStatusSummary"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ToolResultData_: {

            success: boolean;

            data?: components["schemas"]["ToolResultData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_UserInteractionData_: {

            success: boolean;

            data?: components["schemas"]["UserInteractionData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_ValidateSemanticModelData_: {

            success: boolean;

            data?: components["schemas"]["ValidateSemanticModelData"] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_dict_: {

            success: boolean;

            data?: {
                [key: string]: unknown;
            } | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_dict_str__Any__: {

            success: boolean;

            data?: {
                [key: string]: unknown;
            } | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_dict_str__bool__: {

            success: boolean;

            data?: {
                [key: string]: boolean;
            } | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminDatasourceGrantSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminDatasourceGrantSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminDatasourceSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminDatasourceSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminQuotaSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminQuotaSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminRoleSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminRoleSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminSecretSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminSecretSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminSessionSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminSessionSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminUsageSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminUsageSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AdminUserSummary__: {

            success: boolean;

            data?: components["schemas"]["AdminUserSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_AuditLogEntry__: {

            success: boolean;

            data?: components["schemas"]["AuditLogEntry"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_EnterpriseAgentSummary__: {

            success: boolean;

            data?: components["schemas"]["EnterpriseAgentSummary"][] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_dict_str__Any___: {

            success: boolean;

            data?: {
                [key: string]: unknown;
            }[] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        Result_list_str__: {

            success: boolean;

            data?: string[] | null;

            errorCode?: string | null;

            errorMessage?: string | null;
        };

        ResumeChatInput: {

            session_id: string;

            source?: string | null;

            from_event_id?: number | null;
        };

        RunWorkflowRequest: {

            workflow: string;

            datasource: string;

            task: string;

            mode: components["schemas"]["Mode"];

            task_id?: string | null;

            catalog_name?: string | null;

            database_name?: string | null;

            schema_name?: string | null;

            current_date?: string | null;

            subject_path?: string[] | null;

            ext_knowledge?: string | null;
        };

        SSEMessagePayload: {

            message_id: string;

            role: string;

            content?: components["schemas"]["IMessageContent"][];

            depth: number;

            parent_action_id?: string | null;
        };

        SemanticModelInput: {

            table: string;

            yaml: string;
        };

        SetAgentStatusRequest: {

            status: string;
        };

        SetDefaultDatasourceRequest: {

            name: string;
        };

        SetRolePermissionsRequest: {

            permissions?: string[];
        };

        SetUserRolesRequest: {

            role_ids?: string[];
        };

        SqlQueryResultEnvelope: {

            executed_at: string;

            datasource: string;

            row_count: number;

            columns: components["schemas"]["QueryColumnMeta"][];

            rows?: {
                [key: string]: unknown;
            }[];

            sql?: string | null;
        };

        StopChatInput: {

            session_id: string;
        };

        StopExecuteSQLData: {

            execute_task_id: string;

            stopped: boolean;
        };

        StopExecuteSQLInput: {

            execute_task_id: string;
        };

        StreamChatInput: {

            message: string;

            session_id?: string | null;

            model?: string | null;

            plan_mode: boolean;

            source?: string | null;

            interactive?: boolean | null;

            datasource?: string | null;

            catalog?: string | null;

            database?: string | null;

            db_schema?: string | null;

            max_turns: number;

            workspace_root?: string | null;

            table_paths?: string[] | null;

            metric_paths?: string[] | null;

            sql_paths?: string[] | null;

            knowledge_paths?: string[] | null;

            stream_response?: boolean | null;

            context_id?: string | null;

            subagent_id?: string | null;

            prompt_version?: string | null;

            prompt_language: string;

            language?: string | null;

            source_session_id?: string | null;

            permission_mode?: ("normal" | "auto" | "dangerous") | null;
        };

        SubjectListData: {

            subjects: components["schemas"]["SubjectNode"][];
        };

        SubjectNode: {

            name: string;

            type?: components["schemas"]["SubjectNodeType"] | null;

            subject_path?: string[];

            children?: components["schemas"]["SubjectNode"][] | null;
        };

        SubjectNodeType: "directory" | "metric" | "reference_sql";

        SubjectPathInput: {

            subject_path: string[];
        };

        SuccessStoryData: {

            csv_path: string;

            subagent_name: string;

            session_id: string;

            session_link?: string | null;

            timestamp: string;
        };

        SuccessStoryInput: {

            session_id: string;

            sql: string;

            user_message: string;

            subagent_id?: string | null;

            session_link?: string | null;
        };

        SystemStatusSummary: {

            platform_status: string;

            enterprise_enabled: boolean;

            project_id?: string | null;

            current_datasource?: string | null;

            active_tasks: number;

            known_tasks: number;
        };

        TableDetailData: {

            name: string;

            description?: string | null;

            rows?: number | null;

            columns: components["schemas"]["ColumnInfo"][];

            indexes: components["schemas"]["IndexInfo"][];
        };

        TableInfo: {

            table_name: string;

            table_type: string;

            row_count?: number | null;

            columns_count?: number | null;
        };

        TemplateParamDecl: {

            name: string;

            type: "string" | "integer" | "number" | "date" | "boolean" | "string[]" | "integer[]" | "number[]" | "date[]" | "boolean[]";

            required: boolean;
        };

        TokenResponse: {

            access_token: string;

            token_type: string;

            expires_in: number;
        };

        ToolCategoryData: {

            tools?: string[];
        };

        ToolFilterInput: {

            enabled: boolean;

            allowed_tools?: string[] | null;

            blocked_tools?: string[] | null;
        };

        ToolResult: {

            success: 0 | 1;

            error?: string | null;

            result?: unknown | null;
        };

        ToolResultData: {

            call_tool_id: string;

            status: string;
        };

        ToolResultInput: {

            session_id?: string | null;

            call_tool_id: string;

            tool_result: components["schemas"]["ToolResult"];
        };

        UpdateDatasourcesRequest: {

            datasources: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
        };

        UpdateModelsRequest: {

            models?: {
                [key: string]: {
                    [key: string]: unknown;
                };
            } | null;

            target?: string | null;
        };

        UpsertAdminRoleRequest: {

            name: string;

            description?: string | null;

            permissions?: string[];
        };

        UpsertAdminUserRequest: {

            display_name?: string | null;

            email?: string | null;

            enabled: boolean;

            external_user_id?: string | null;

            department?: string | null;

            title?: string | null;

            last_seen_at?: string | null;
        };

        UpsertDatasourceGrantRequest: {

            effect: unknown;

            scope?: unknown;
        };

        UpsertEnterpriseAgentRequest: {

            name?: string | null;

            description?: string | null;

            node_class: string;

            status: string;

            datasource_id?: string | null;

            artifact_slug?: string | null;

            prompt_template?: string | null;

            prompt_language: string;

            prompt_version: string | null;

            tools?: string[];

            mcp?: string[];

            skills?: string[];

            scoped_context?: {
                [key: string]: unknown;
            };

            rules?: string[];

            max_turns: number;
            acl?: components["schemas"]["AgentAcl"];
        };

        UpsertQuotaRequest: {

            subject_type: unknown;

            subject_id?: unknown;

            resource: unknown;

            limit: unknown;

            window_seconds: unknown;

            enabled: unknown;
        };

        UpsertSecretRequest: {

            provider: unknown;

            reference: unknown;

            description?: unknown;

            enabled: unknown;
        };

        UserInteractionData: {

            interaction_key: string;

            submitted: boolean;
        };

        UserInteractionInput: {

            session_id: string;

            interaction_key: string;

            input: string[][];
        };

        ValidateSemanticModelData: {

            valid: boolean;

            invalid_message?: string[] | null;
        };

        ValidationError: {

            loc: (string | number)[];

            msg: string;

            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    stream_chat_api_v1_chat_stream_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StreamChatInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stream_chat_feedback_api_v1_chat_feedback_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackChatInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resume_chat_api_v1_chat_resume_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResumeChatInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stop_chat_api_v1_chat_stop_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StopChatInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compact_chat_session_api_v1_chat_sessions__session_id__compact_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {

                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_CompactSessionData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sessions_api_v1_chat_sessions_get: {
        parameters: {
            query?: {

                subagent_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ChatSessionData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_session_api_v1_chat_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {

                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ChatSessionData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_chat_history_api_v1_chat_history_get: {
        parameters: {
            query: {

                session_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ChatHistoryData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_user_interaction_api_v1_chat_user_interaction_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserInteractionInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_UserInteractionData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    insert_message_api_v1_chat_insert_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InsertMessageInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_InsertMessageData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_tool_result_api_v1_chat_tool_result_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolResultInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ToolResultData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    execute_sql_api_v1_sql_execute_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExecuteSQLInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ExecuteSQLData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stop_execute_sql_api_v1_sql_stop_execute_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StopExecuteSQLInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_StopExecuteSQLData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    execute_context_api_v1_context__context_type__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_type: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ExecuteContextInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ExecuteContextData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    execute_internal_command_api_v1_internal__command__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                command: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["InternalCommandInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_InternalCommandData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_catalogs_api_v1_catalog_list_get: {
        parameters: {
            query?: {

                datasource_id?: string | null;

                catalog_name?: string | null;

                database_name?: string | null;

                schema_name?: string | null;

                include_sys_schemas?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_DatabasesData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_table_detail_api_v1_table_detail_get: {
        parameters: {
            query: {

                table: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_GetTableDetailData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_semantic_model_api_v1_semantic_model_get: {
        parameters: {
            query: {

                table: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_GetSemanticModelData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_semantic_model_api_v1_semantic_model_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SemanticModelInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    validate_semantic_model_api_v1_semantic_model_validate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SemanticModelInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ValidateSemanticModelData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_subject_tree_api_v1_subject_tree_get: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_SubjectListData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_directory_api_v1_subject_tree_create_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateDirectoryInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rename_subject_api_v1_subject_tree_rename_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RenameSubjectInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_subject_api_v1_subject_tree_delete_delete: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeleteSubjectInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_metric_api_v1_subject_tree_metric_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubjectPathInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MetricInfo_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_metric_dimensions_api_v1_subject_tree_metric_dimensions_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubjectPathInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MetricDimensionsData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_metric_api_v1_subject_tree_metric_preview_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MetricPreviewInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MetricPreviewData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_metric_api_v1_subject_tree_metric_create_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditMetricInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_metric_api_v1_subject_tree_metric_edit_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditMetricInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_reference_sql_api_v1_subject_tree_reference_sql_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubjectPathInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ReferenceSQLInfo_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_reference_sql_api_v1_subject_tree_reference_sql_create_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReferenceSQLInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_reference_sql_api_v1_subject_tree_reference_sql_edit_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReferenceSQLInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_semantic_model_api_v1_subject_tree_semantic_model_edit_post: {
        parameters: {
            query?: {

                datasource_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditSemanticModelInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_subject_list_api_v1_subject_list_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_SubjectListData_"];
                };
            };
        };
    };
    create_directory_api_v1_subject_create_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateDirectoryInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rename_subject_api_v1_subject_rename_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RenameSubjectInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_subject_api_v1_subject_delete_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeleteSubjectInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_metric_api_v1_subject_metric_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubjectPathInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MetricInfo_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_metric_dimensions_api_v1_subject_metric_dimensions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubjectPathInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MetricDimensionsData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_metric_api_v1_subject_metric_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MetricPreviewInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MetricPreviewData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_reference_sql_api_v1_subject_reference_sql_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubjectPathInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ReferenceSQLInfo_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_reference_sql_api_v1_subject_reference_sql_create_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReferenceSQLInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_reference_sql_api_v1_subject_reference_sql_edit_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReferenceSQLInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_metric_api_v1_subject_metric_create_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditMetricInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_metric_api_v1_subject_metric_edit_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditMetricInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_semantic_model_api_v1_subject_semantic_model_edit_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditSemanticModelInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_agent_config_endpoint_api_v1_config_agent_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentConfigSummaryData_"];
                };
            };
        };
    };
    update_datasources_endpoint_api_v1_config_datasources_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateDatasourcesRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MutationResultData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_models_endpoint_api_v1_config_models_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateModelsRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MutationResultData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    probe_model_connectivity_endpoint_api_v1_config_models_test_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProbeModelRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ProbeResultData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    probe_datasource_connectivity_endpoint_api_v1_config_datasources_test_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProbeDatasourceRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ProbeResultData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_models_api_v1_models_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ModelsData_"];
                };
            };
        };
    };
    list_servers_api_v1_mcp_servers_get: {
        parameters: {
            query?: {

                server_type?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_server_api_v1_mcp_servers_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AddServerInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_server_api_v1_mcp_servers__server_name__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_connectivity_api_v1_mcp_servers__server_name__connectivity_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tools_api_v1_mcp_servers__server_name__tools_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    call_tool_api_v1_mcp_servers__server_name__tools__tool_name__call_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_name: string;
                tool_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CallToolInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_tool_filter_api_v1_mcp_servers__server_name__filters_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_tool_filter_api_v1_mcp_servers__server_name__filters_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolFilterInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_tool_filter_api_v1_mcp_servers__server_name__filters_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_Dict_str__Any__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_kb_upload_api_v1_kb_uploads_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_kb_upload_api_v1_kb_uploads_post"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KbUploadRecord"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_kb_upload_api_v1_kb_uploads__upload_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KbUploadRecord"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_kb_upload_api_v1_kb_uploads__upload_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                upload_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KbUploadDeleteResponse"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    bootstrap_kb_api_v1_kb_bootstrap_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BootstrapKbInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_bootstrap_api_v1_kb_bootstrap__stream_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {

                stream_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    bootstrap_docs_api_v1_kb_bootstrap_docs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BootstrapDocInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_doc_bootstrap_api_v1_kb_bootstrap_docs__stream_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {

                stream_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_agent_use_tools_api_v1_agent_use_tools_get: {
        parameters: {
            query: {

                agent_type: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentUseToolsData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_agent_api_v1_agent_get: {
        parameters: {
            query: {

                agent_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_GetAgentData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agents_api_v1_agent_list_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentListData_"];
                };
            };
        };
    };
    create_agent_api_v1_agent_create_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateAgentInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentMutationData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_agent_api_v1_agent_edit_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EditAgentInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentMutationData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_agent_api_v1_agent_delete_delete: {
        parameters: {
            query: {

                agent_id: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentMutationData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_available_tools_api_v1_agent_tools_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentToolsData_"];
                };
            };
        };
    };
    data_visualization_api_v1_data_visualization_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DataVisualizationRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_DataVisualizationData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    execute_tool_api_v1_tools__tool_name__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {

                tool_name: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                } | null;
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_FuncToolResult_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_success_story_api_v1_success_stories_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SuccessStoryInput"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_SuccessStoryData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dashboard_detail_api_v1_dashboard_detail_get: {
        parameters: {
            query: {

                slug: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_DashboardDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_dashboard_query_api_v1_dashboard_query_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DashboardQueryRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_SqlQueryResultEnvelope_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_report_detail_api_v1_report_detail_get: {
        parameters: {
            query: {

                slug: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ReportDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_me_api_v1_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_MeSummary_"];
                };
            };
        };
    };
    get_my_permissions_api_v1_me_permissions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_str__"];
                };
            };
        };
    };
    get_my_datasource_grants_api_v1_me_datasource_grants_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_str__Any__"];
                };
            };
        };
    };
    get_my_features_api_v1_me_features_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_str__bool__"];
                };
            };
        };
    };
    get_my_sessions_api_v1_me_sessions_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ChatSessionData_"];
                };
            };
        };
    };
    get_my_usage_api_v1_me_usage_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_dict_str__Any___"];
                };
            };
        };
    };
    list_dashboards_api_v1_dashboards_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_List_ArtifactManifest__"];
                };
            };
        };
    };
    get_dashboard_detail_api_v1_dashboards__slug__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_DashboardDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dashboard_share_acl_api_v1_dashboards__slug__acl_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ArtifactShare_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_dashboard_share_acl_api_v1_dashboards__slug__acl_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArtifactShareUpdate"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ArtifactShare_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dashboard_html_by_path_api_v1_dashboards__slug__html_get: {
        parameters: {
            query?: {

                query_endpoint?: string;
            };
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_reports_api_v1_reports_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_List_ArtifactManifest__"];
                };
            };
        };
    };
    get_report_detail_api_v1_reports__slug__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ReportDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_report_share_acl_api_v1_reports__slug__acl_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ArtifactShare_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_report_share_acl_api_v1_reports__slug__acl_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArtifactShareUpdate"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ArtifactShare_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_report_html_by_path_api_v1_reports__slug__html_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_artifacts_api_v1_admin_artifacts_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_List_AdminArtifactSummary__"];
                };
            };
        };
    };
    get_admin_artifact_acl_api_v1_admin_artifacts__artifact_type___slug__acl_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                artifact_type: "report" | "dashboard";
                slug: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ArtifactAcl_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_admin_artifact_acl_api_v1_admin_artifacts__artifact_type___slug__acl_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                artifact_type: "report" | "dashboard";
                slug: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArtifactAcl"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_ArtifactAcl_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_available_agents_api_v1_agents_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_EnterpriseAgentSummary__"];
                };
            };
        };
    };
    get_available_agent_tools_api_v1_agents__agent_id__tools_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentUseToolsData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_available_agent_api_v1_agents__agent_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_EnterpriseAgentDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_agent_tools_api_v1_admin_agents_tools_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentToolsData_"];
                };
            };
        };
    };
    get_admin_agent_tool_reference_api_v1_admin_agents_tool_reference_get: {
        parameters: {
            query?: {

                node_class?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentUseToolsData_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_agents_api_v1_admin_agents_get: {
        parameters: {
            query?: {

                status?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_EnterpriseAgentSummary__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_admin_agent_api_v1_admin_agents__agent_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_EnterpriseAgentDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upsert_admin_agent_api_v1_admin_agents__agent_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpsertEnterpriseAgentRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_EnterpriseAgentDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_admin_agent_api_v1_admin_agents__agent_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_str__bool__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_admin_agent_status_api_v1_admin_agents__agent_id__status_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetAgentStatusRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_EnterpriseAgentDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_admin_agent_acl_api_v1_admin_agents__agent_id__acl_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentAcl_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_admin_agent_acl_api_v1_admin_agents__agent_id__acl_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentAcl"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AgentAcl_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_datasources_endpoint_api_v1_admin_datasources_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminDatasourceSummary__"];
                };
            };
        };
    };
    list_admin_datasource_grants_api_v1_admin_datasource_grants_get: {
        parameters: {
            query?: {

                subject_type?: string | null;

                subject_id?: string | null;

                datasource_key?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminDatasourceGrantSummary__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_admin_datasource_grant_api_v1_admin_datasource_grants__subject_type___subject_id___datasource_key__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                subject_type: string;
                subject_id: string;
                datasource_key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminDatasourceGrantSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upsert_admin_datasource_grant_api_v1_admin_datasource_grants__subject_type___subject_id___datasource_key__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                subject_type: string;
                subject_id: string;
                datasource_key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpsertDatasourceGrantRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminDatasourceGrantSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_admin_datasource_grant_api_v1_admin_datasource_grants__subject_type___subject_id___datasource_key__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                subject_type: string;
                subject_id: string;
                datasource_key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_project_default_datasource_endpoint_api_v1_admin_datasource_default_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetDefaultDatasourceRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_audit_logs_api_v1_admin_audit_logs_get: {
        parameters: {
            query?: {
                limit?: number;
                user_id?: string | null;
                action?: string | null;
                resource_type?: string | null;
                resource_id?: string | null;
                decision?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AuditLogEntry__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_audit_logs_api_v1_admin_audit_logs_export_get: {
        parameters: {
            query?: {
                limit?: number;
                user_id?: string | null;
                action?: string | null;
                resource_type?: string | null;
                resource_id?: string | null;
                decision?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_sessions_api_v1_admin_sessions_get: {
        parameters: {
            query?: {

                user_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminSessionSummary__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_admin_session_api_v1_admin_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminSessionDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_admin_session_api_v1_admin_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stop_admin_session_api_v1_admin_sessions__session_id__stop_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_users_api_v1_admin_users_get: {
        parameters: {
            query?: {

                enabled?: boolean | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminUserSummary__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_admin_user_api_v1_admin_users__user_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminUserDetail_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upsert_admin_user_api_v1_admin_users__user_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpsertAdminUserRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminUserSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disable_admin_user_api_v1_admin_users__user_id__disable_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminUserSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    enable_admin_user_api_v1_admin_users__user_id__enable_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminUserSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_roles_api_v1_admin_roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminRoleSummary__"];
                };
            };
        };
    };
    get_admin_role_api_v1_admin_roles__role_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminRoleSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upsert_admin_role_api_v1_admin_roles__role_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpsertAdminRoleRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminRoleSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_admin_role_api_v1_admin_roles__role_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_admin_role_permissions_api_v1_admin_roles__role_id__permissions_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                role_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetRolePermissionsRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminRoleSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_admin_user_roles_api_v1_admin_users__user_id__roles_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminUserRolesSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_admin_user_roles_api_v1_admin_users__user_id__roles_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetUserRolesRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminUserRolesSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_quotas_api_v1_admin_quotas_get: {
        parameters: {
            query?: {

                subject_type?: string | null;

                subject_id?: string | null;

                resource?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminQuotaSummary__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upsert_admin_quota_api_v1_admin_quotas_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpsertQuotaRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminQuotaSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_usage_api_v1_admin_usage_get: {
        parameters: {
            query?: {

                subject_type?: string | null;

                subject_id?: string | null;

                resource?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminUsageSummary__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_admin_secrets_api_v1_admin_secrets_get: {
        parameters: {
            query?: {

                prefix?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_list_AdminSecretSummary__"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_admin_secret_api_v1_admin_secrets__name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminSecretSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upsert_admin_secret_api_v1_admin_secrets__name__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpsertSecretRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_AdminSecretSummary_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_admin_secret_api_v1_admin_secrets__name__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_dict_"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_system_status_api_v1_system_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Result_SystemStatusSummary_"];
                };
            };
        };
    };
    root__get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    health_check_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    authenticate_auth_token_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
        };
    };
    run_workflow_workflows_run_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunWorkflowRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_feedback_workflows_feedback_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackRequest"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackResponse"];
                };
            };

            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
