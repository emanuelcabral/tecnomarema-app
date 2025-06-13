function inhabilitar(){
    alert ("Esta función está inhabilitada.\n\nDisculpe las molestias.")
    return false
}

document.oncontextmenu = inhabilitar


//deshabilitar el f12 ↓↓↓
document.onkeydown = function(){return false};