let words = [
    "google",
    "New York University",
    "Spathis",
    "github",
    "pornhub",
    "quit",
  ];
  
  // Variable for displaying the results on the canvas
  let predictedWord = "";
  let tracerouteCommand = ""; // 用于存储生成的 traceroute 指令
  
  function preload() {
    // Options for the SpeechCommands18w model, the default probabilityThreshold is 0
    let options = { probabilityThreshold: 0.7 };
    // Load SpeechCommands18w sound classifier model
    classifier = ml5.soundClassifier("SpeechCommands18w", options);
  }
  
  function setup() {
    noCanvas();
    // Classify the sound from microphone in real time
    classifier.classify(gotResult);
  }
  
  function draw() {
    // Once the model outputs results, display the predicted word
    if (predictedWord !== "") {
      console.log("Predicted Word:", predictedWord);
      console.log("Traceroute Command:", tracerouteCommand);
    }
  }
  
  // A function to run when we get any errors and the results
  function gotResult(results) {
    if (results && results.length > 0) {
      predictedWord = results[0].label;
      tracerouteCommand = mapToTraceroute(predictedWord);
      console.log("执行命令:", tracerouteCommand);
      if (tracerouteCommand.startsWith('traceroute ')) {
        window.api.runTraceroute(tracerouteCommand);
      }
      if (tracerouteCommand === 'exit') {
        window.close();
      }
    }
  }
  
  // Function to map recognized words to traceroute commands
  function mapToTraceroute(word) {
    // Define a mapping from recognized words to traceroute commands
    const tracerouteMap = {
      google: "traceroute google.com",
      "New York University": "traceroute nyu.edu",
      Spathis: "traceroute spathis.median.com",
      github: "traceroute github.io",
      pornhub: "traceroute pornhub.com",
      quit: "exit", // Special case for quitting
    };
  
    // Return the corresponding traceroute command or a default message
    return tracerouteMap[word] || "Command not recognized";
  }