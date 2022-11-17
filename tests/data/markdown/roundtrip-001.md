# Header

Here's some text and an image

![some text](image.png)
![some text](image.png "a title")
![some text]("a bogus title")

and then some more text and another image

![some [other] text](image.png "some ) title")

```auspiceMainDisplayMarkdown
right hand panel content

![some image](image.png "title \\" foo")

more content
```

now some more advanced images

![full][full]
![collapsed][]
![shortcut]

that use references

[full]: image.png
[collapsed]: image.png
[shortcut]: image.png
[unused]: https://example.com

another code fence:

    ```python
    print("hello markdown")
    ```

and a code block:

    foo
    bar
    baz

and then some weirder image forms:

![abc
def][foo]

![abc
def][
foo]

![alt](
https://secure.gravatar.com/avatar/c2f056279f6573478e3b48e95b9b338b
"abc
def")
