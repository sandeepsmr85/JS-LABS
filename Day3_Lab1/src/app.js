// var chocolates = [
//   "green", "green", "green", "silver", "blue", "crimson", "purple", "red", "crimson", "purple",
//   "purple", "green", "pink", "blue", "red", "silver", "crimson", "purple", "silver", "silver",
//   "red", "green", "red", "silver", "pink", "crimson", "purple", "green", "red", "silver",
//   "crimson", "pink", "silver", "blue", "pink", "crimson", "crimson", "crimson", "red", "purple",
//   "purple", "green", "pink", "blue", "red", "crimson", "silver", "purple", "purple", "purple",
//   "red", "purple", "red", "blue", "silver", "green", "crimson", "silver", "blue", "crimson",
//   "purple", "green", "pink", "green", "red", "silver", "crimson", "blue", "green", "red",
//   "red", "pink", "blue", "silver", "pink", "crimson", "purple", "green", "red", "blue",
//   "red", "purple", "silver", "blue", "pink", "silver", "crimson", "silver", "blue", "purple",
//   "purple", "green", "blue", "blue", "red", "red", "silver", "purple", "silver", "crimson"
// ];

//Trial 1: Add ___ chocolates of ____ color
function addChocolates(chocolates, color, number) {
  if (!number < 0) {
    for (let i = 0; i < number; i++)
      chocolates.unshift(color);
  }
  else
    return
}

var temp = ["green", "red"];
addChocolates(temp, "green", -5);
console.log(temp);

//Trial 2: Remove ___ chocolates from the top the dispenser
function removeChocolates(chocolates, number) {
  if (number > chocolates.length) {
    return "invalid number"
  }
  else {
    let removedChoco = [];
    for (let i = 0; i < number; i++)
      removedChoco.push(chocolates.shift());
    return removedChoco;
  }
}

//Trial 3: Dispense ___ chocolates
function dispenseChocolates(chocolates, number) {
  if (number <= 0) {
    return "dispensed chocolate value can't be zero or negative"
  }
  else {
    let dispensedChoco = [];
    for (let i = 0; i < number; i++)
      dispensedChoco.push(chocolates.pop());
    return dispensedChoco;
  }
}

//Trial 4: Dispense ___ chocolates of ____ color
function dispenseChocolatesOfColor(chocolates, number, color) {
  if (number <= 0) {
    return "dispensed chocolate value can't be zero or negative";
  }
  else {
    let removed = [];
    for (let i = 0; i < number; i++) {
      let indexOf = chocolates.lastIndexOf(color);
      removed.push(chocolates[indexOf]);
      chocolates.splice(indexOf, 1);
    }
    return removed;
  }
}

//Trial 5: Display ___ chocolates of each color. Return array of numbers [green, silver, blue, crimson, purple, red, pink]
function noOfChocolates(chocolates) {
  let types = [];
  chocolates.forEach(e => (types.indexOf(e) == -1) ? types.push(e) : "");
  let numbers = [];
  for (let i = 0; i < types.length; i++) {
    numbers[i] = chocolates.reduce((acc, val) => acc += (val == types[i]) ? 1 : 0, 0);
  }
  return numbers;
}

//Trial 6: Sort chocolates based on count in each color. Return array of colors
function sortChocolateBasedOnCount(chocolates) {
  let chocolatesObj = chocolates.reduce(function (sortedChoc, choc) {
    if (choc in sortedChoc) {
      sortedChoc[choc]++;
    } else {
      sortedChoc[choc] = 1;
    }
    return sortedChoc;
  }, {});
  let sortedArray = chocolates.sort((a, b) => {
    if (chocolatesObj[b] > chocolatesObj[a]) {
      return 1;
    }
    if (chocolatesObj[b] < chocolatesObj[a]) {
      return -1;
    }
    if (a > b) {
      return 1;
    }
    if (a < b) {
      return -1;
    }
  });
  chocolates = sortedArray;
}

//Trial 7: Change ___ chocolates of ____ color to ____ color
function changeChocolateColor(chocolates, number, color, finalColor) {
  let chocChanged = 0;
  chocolates = chocolates.map((e) => {
    if (e == color) {
      chocChanged++;
      if (chocChanged <= number)
        return finalColor;
      else
        return e;
    } else {
      return e;
    }
  });
  return chocolates;
}

//Trial 8: Change all chocolates of ____ color to ____ color and return [countOfChangedColor, chocolates]
function changeChocolateColorAllOfxCount(chocolates, color, finalColor) {
  let changed = chocolates.map(e => (e == color) ? finalColor : e);
  let count = changed.reduce((acc, val) => acc += (val == finalColor) ? 1 : 0, 0);
  return [count, changed];
}


//Challenge 1: Remove one chocolate of ____ color from the top
function removeChocolateOfColor(chocolates, color) {
  let choc = "";
  for (let i = 0; i < chocolates.length; i++) {
    if (chocolates[i] === color) {
      choc = chocolates[i];
      arr.splice(i, 1);
      break;
    }
  }
  return choc;
}

//Challenge 2: Dispense 1 rainbow colored colored chocolate for every 3 chocolates of the same color dispensed
function dispenseRainbowChocolates(chocolates, number) {
  dispenseChocolates = dispenseChocolates(chocolates, number);
  let frequency = [dispenseChocolates.length];
  let visited = -1;

  for (let i = 0; i < dispenseChocolates.length; i++) {
    let count = 1;
    for (let j = i + 1; j < dispenseChocolates.length; j++) {
      if (dispenseChocolates[i] == dispenseChocolates[j]) {
        count++;
        frequency[j] = visited;
      }
    }
    if (frequency[i] != visited)
      frequency[i] = count;
  }

  let rainbowChocolates = 0;
  for (let i = 0; i < frequency.length; i++) {
    if (frequency[i] != visited && frequency[i] % 3 == 0) {
      rainbowChocolates += frequency[i] / 3;
    }
  }
  return rainbowChocolates;
}