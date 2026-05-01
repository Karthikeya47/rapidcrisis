// Empty service worker for Firebase Messaging on Web
// Required to prevent flutter's firebase_messaging from crashing on init
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyAW5mIVNn4p5etMXAkpcRmrFlm8uTfDl04",
  appId: "1:1051430206062:web:e9b02b11f1bf1ab221c47f",
  messagingSenderId: "1051430206062",
  projectId: "project-e82fa8f3-3868-42a9-a35",
});

const messaging = firebase.messaging();
