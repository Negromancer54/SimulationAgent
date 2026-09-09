console.log("SimulationAgent Bridge: content script loaded");


function validateTaskRequest(message) {
    if (message.type !== "task_request") {
        return {
            valid: false,
            code: "INVALID_REQUEST_TYPE",
            message: "Invalid request type."
        };
    }
	if (
        typeof message.request_id !== "string" ||
        message.request_id.trim() === ""
    ) {
        return {
            valid: false,
            code: "INVALID_REQUEST_ID",
            message: "Request must contain a non-empty request_id."
        };
    }

    if (
        !message.task ||
        typeof message.task !== "object" ||
        Array.isArray(message.task)
    ) {
        return {
            valid: false,
            code: "INVALID_TASK",
            message: "Request must contain a valid task object."
        };
    }

    if (
        typeof message.task.task_id !== "string" ||
        message.task.task_id.trim() === ""
    ) {
        return {
            valid: false,
            code: "INVALID_TASK_ID",
            message: "Task must contain a non-empty task_id."
        };
    }

    return {
        valid: true
    };
}


function sendSimulationAgentTask(requestId, task) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
            {
                type: "task_request",
                request_id: requestId,
                task: task,
            },
            (response) => {
                if (chrome.runtime.lastError) {
                    reject(
                        new Error(
                            chrome.runtime.lastError.message
                        )
                    );

                    return;
                }

                if (!response) {
                    reject(
                        new Error(
                            "No response from background worker."
                        )
                    );

                    return;
                }

                if (response.success === false) {
                    reject(
                        new Error(
                            response.error?.message ||
                            response.error ||
                            "SimulationAgent Bridge request failed."
                        )
                    );

                    return;
                }

                resolve(response);
            }
        );
    });
}


window.addEventListener(
    "message",
    (event) => {
        if (event.source !== window) {
            return;
        }

        const message = event.data;

        /*
         * IMPORTANT:
         * Ignore every message that did not originate
         * from the page-side Bridge API.
         *
         * This prevents the content script from processing
         * its own responses or unrelated ChatGPT messages.
         */
		if (
			!message ||
			message.source !== "simulationagent-page"
		) {
			return;
		}

		const validation = validateTaskRequest(message);

        if (!validation.valid) {
            console.error(
                "SimulationAgent Bridge: invalid task request:",
                validation
            );

            window.postMessage(
                {
                    source: "simulationagent-bridge",
                    type: "task_response",
                    request_id:
                        typeof message.request_id === "string"
                            ? message.request_id
                            : null,
                    success: false,
                    error: {
                        code: validation.code,
                        message: validation.message,
                    },
                },
                "*"
            );

            return;
        }

        const requestId = message.request_id;

        console.log(
            "SimulationAgent Bridge: task request received from page:",
            requestId
        );

        sendSimulationAgentTask(
            requestId,
            message.task
        )
            .then((response) => {
                window.postMessage(
                    {
                        source: "simulationagent-bridge",
                        type: "task_response",
                        request_id: requestId,
                        success: true,
                        result: response.result,
                    },
                    "*"
                );
            })
            .catch((error) => {
                window.postMessage(
                    {
                        source: "simulationagent-bridge",
                        type: "task_response",
                        request_id: requestId,
                        success: false,
                        error: {
                            code: "BRIDGE_REQUEST_FAILED",
                            message: error.message,
                        },
                    },
                    "*"
                );
            });
    }
);


window.postMessage(
    {
        source: "simulationagent-bridge",
        type: "bridge_ready",
    },
    "*"
);


console.log(
    "SimulationAgent Bridge: page message API ready"
);