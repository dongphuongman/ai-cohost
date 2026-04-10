chrome.runtime.onInstalled.addListener(() => {
  console.log("AI Co-host extension installed");
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "GET_AUTH_TOKEN") {
    chrome.storage.local.get(["authToken"], (result) => {
      sendResponse({ token: result.authToken ?? null });
    });
    return true;
  }
});
