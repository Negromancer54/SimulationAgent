(function () {
    "use strict";

    if (window.SimulationAgentBridge) {
        return;
    }

    let requestCounter = 0;
    const pendingRequests = new Map();

    function generateRequestId() {
        requestCounter += 1;

        return (
            "PAGE-" +
            Date.now().toString(36) +
            "-" +
            requestCounter.toString(36)
        );
    }

    function sendTask(task, options = {}) {
        if (
            !task ||
            typeof task !== "object" ||
            Array.isArray(task)
        ) {
            return Promise.reject({
                code: "INVALID_TASK",
                message: "Task must be an object."
            });
        }

        const requestId = generateRequestId();

        const timeout =
            typeof options.timeout === "number" &&
            options.timeout > 0
                ? options.timeout
                : 30000;

        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                pendingRequests.delete(requestId);

                reject({
                    code: "TIMEOUT",
                    message:
                        "SimulationAgent Bridge request timed out."
                });
            }, timeout);

            pendingRequests.set(requestId, {
                resolve,
                reject,
                timer
            });

            window.postMessage(
                {
                    source: "simulationagent-page",
                    type: "task_request",
                    request_id: requestId,
                    task: task
                },
                "*"
            );
        });
    }

    function handleBridgeMessage(event) {
        if (event.source !== window) {
            return;
        }

        const message = event.data;

        if (
            !message ||
            message.source !== "simulationagent-bridge" ||
            message.type !== "task_response"
        ) {
            return;
        }

        const requestId = message.request_id;

        if (
            typeof requestId !== "string" ||
            requestId.trim() === ""
        ) {
            return;
        }

        const pending = pendingRequests.get(requestId);

        if (!pending) {
            return;
        }

        pendingRequests.delete(requestId);
        clearTimeout(pending.timer);

        if (message.success === false) {
            pending.reject(
                message.error || {
                    code: "BRIDGE_REQUEST_FAILED",
                    message:
                        "SimulationAgent Bridge request failed."
                }
            );

            return;
        }

        pending.resolve(message.result);
    }

    window.addEventListener(
        "message",
        handleBridgeMessage
    );

    window.SimulationAgentBridge = Object.freeze({
        sendTask
    });
})();
