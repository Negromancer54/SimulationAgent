console.log("SimulationAgent Bridge: background worker loaded");

let nativePort = null;
const pendingTasks = new Map();


function connectNativeHost() {
    if (nativePort) {
        return nativePort;
    }

    nativePort = chrome.runtime.connectNative(
        "com.simulationagent.bridge"
    );

    nativePort.onMessage.addListener((message) => {
        console.log(
            "Received from native host:",
            message
        );

        console.log(
            "FULL NATIVE MESSAGE:",
            JSON.stringify(message, null, 2)
        );

        if (message?.type === "task_result") {
            handleTaskResult(message);
        }
    });

	nativePort.onDisconnect.addListener(() => {
		const errorMessage =
			chrome.runtime.lastError?.message ||
			"Native host disconnected.";

		console.error(
			"Native host disconnected:",
			errorMessage
		);

		nativePort = null;

		for (const [taskId, pending] of pendingTasks) {
			pendingTasks.delete(taskId);

			pending.reject({
				code: "NATIVE_HOST_DISCONNECTED",
				message: errorMessage,
			});
		}
	});

    console.log("Connected to native host");

    return nativePort;
}


function handleTaskResult(message) {
    const taskId = message?.task_id;

    if (!taskId) {
        console.error(
            "Received task_result without task_id:",
            message
        );

        return;
    }

    const pending = pendingTasks.get(taskId);

    if (!pending) {
        console.warn(
            "Received task_result for unknown task:",
            taskId
        );

        return;
    }

    pendingTasks.delete(taskId);

    pending.resolve(message.result);
}


function sendTask(task) {
    if (!task || typeof task !== "object") {
        return Promise.reject(
            new Error("Task must be an object.")
        );
    }

    if (
        typeof task.task_id !== "string" ||
        task.task_id.trim() === ""
    ) {
        return Promise.reject(
            new Error("Task must contain a non-empty task_id.")
        );
    }

    const taskId = task.task_id;

    if (pendingTasks.has(taskId)) {
        return Promise.reject(
            new Error(
                `Task is already pending: ${taskId}`
            )
        );
    }

    const port = connectNativeHost();

    return new Promise((resolve, reject) => {
        pendingTasks.set(taskId, {
            resolve,
            reject,
        });

        try {
            port.postMessage({
                type: "task",
                task: task,
            });

            console.log(
                "Task sent to native host:",
                taskId
            );
        } catch (error) {
            pendingTasks.delete(taskId);
            reject(error);
        }
    });
}


function sendTestTask() {
    const task = {
        task_id: "BRIDGE-TXN-001",
        description:
            "Native Messaging transactional integration test.",
        edits: [
            {
                type: "create",
                path: "bridge_task_probe.txt",
                content: "Bridge transactional test file.\n"
            }
        ],
        expected_paths: [
            "bridge_task_probe_expected.txt"
        ]
    };

    console.log(
        "Sending manual transactional test task"
    );

    return sendTask(task)
        .then((result) => {
            console.log(
                "Task result received:",
                result
            );

            return result;
        })
        .catch((error) => {
            console.error(
                "Task failed at bridge level:",
                error
            );

            throw error;
        });
}


chrome.runtime.onMessage.addListener(
    (message, sender, sendResponse) => {
        if (message?.type === "bridge_test") {
            console.log(
                "Received from content script:",
                message.message
            );

            const port = connectNativeHost();

            port.postMessage({
                type: "ping"
            });

            port.postMessage({
                type: "agent_test"
            });

            sendResponse({
                type: "bridge_test_response",
                message: "Ping sent to native host"
            });

            return true;
        }

        if (message?.type === "task_request") {
            console.log(
                "Received SimulationAgent task request:",
                message.request_id
            );

            const requestId = message.request_id;
            const task = message.task;

            sendTask(task)
                .then((result) => {
                    sendResponse({
                        type: "task_response",
                        request_id: requestId,
                        success: true,
                        result: result,
                    });
                })
				.catch((error) => {
					sendResponse({
						type: "task_response",
						request_id: requestId,
						success: false,
						error: {
							code:
								error?.code ||
								"BRIDGE_REQUEST_FAILED",
							message:
								error?.message ||
								String(error),
						},
					});
				});

            return true;
        }
    }
);